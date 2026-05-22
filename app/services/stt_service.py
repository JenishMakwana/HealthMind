from __future__ import annotations

import asyncio
import os
import tempfile
from functools import lru_cache
from typing import Any

from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings, get_settings


class QwenSTTService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model: Any | None = None

    def _resolve_device(self) -> str:
        if self.settings.stt_device != "auto":
            return self.settings.stt_device

        try:
            import torch

            return "cuda:0" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def _resolve_dtype(self):
        if self.settings.stt_dtype != "auto":
            return self.settings.stt_dtype

        try:
            import torch

            if self._resolve_device().startswith("cuda"):
                return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            return torch.float32
        except Exception:
            return "float32"

    def _load_model(self):
        if self._model is not None:
            return self._model

        try:
            from qwen_asr import Qwen3ASRModel
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Qwen ASR dependencies are not installed. Run pip install -r requirements.txt.",
            ) from exc

        device = self._resolve_device()
        dtype = self._resolve_dtype()

        # device_map must NOT be passed on CPU — it triggers a meta-tensor
        # copy error with large models (PyTorch limitation on CPU offload).
        # On CUDA, device_map routes layers to the GPU automatically.
        load_kwargs: dict = {"dtype": dtype, "max_new_tokens": self.settings.stt_max_new_tokens}
        if device.startswith("cuda"):
            load_kwargs["device_map"] = device

        self._model = Qwen3ASRModel.from_pretrained(
            self.settings.stt_model,
            **load_kwargs,
        )
        hf_model = getattr(self._model, "model", None)
        processor = getattr(self._model, "processor", None)
        tokenizer = getattr(processor, "tokenizer", None)

        if hf_model is not None and hasattr(hf_model, "generation_config"):
            generation_config = hf_model.generation_config
            generation_config.max_new_tokens = self.settings.stt_max_new_tokens
            generation_config.do_sample = False
            if hasattr(generation_config, "temperature"):
                generation_config.temperature = None
            if tokenizer is not None:
                eos_token_id = getattr(tokenizer, "eos_token_id", None)
                pad_token_id = getattr(tokenizer, "pad_token_id", None) or eos_token_id
                if pad_token_id is not None:
                    generation_config.pad_token_id = pad_token_id
                    if getattr(tokenizer, "pad_token_id", None) is None:
                        tokenizer.pad_token_id = pad_token_id
                if eos_token_id is not None:
                    generation_config.eos_token_id = eos_token_id

        return self._model

    def _transcribe_sync(self, audio_path: str) -> dict[str, Any]:
        model = self._load_model()
        result = model.transcribe(
            audio=audio_path,
            context=self.settings.stt_context,
            language=self.settings.stt_language,
        )

        if isinstance(result, (list, tuple)) and result:
            first = result[0]
            return {
                "text": str(getattr(first, "text", "")).strip(),
                "language": getattr(first, "language", None) or self.settings.stt_language,
                "duration_seconds": getattr(first, "duration_seconds", None),
            }

        if isinstance(result, str):
            return {"text": result.strip(), "language": self.settings.stt_language}

        if isinstance(result, dict):
            text = str(result.get("text", "")).strip()
            return {
                "text": text,
                "language": result.get("language") or self.settings.stt_language,
                "duration_seconds": result.get("duration_seconds"),
            }

        if hasattr(result, "text"):
            return {
                "text": str(getattr(result, "text", "")).strip(),
                "language": getattr(result, "language", None) or self.settings.stt_language,
                "duration_seconds": getattr(result, "duration_seconds", None),
            }

        text = str(result).strip()
        return {"text": text, "language": self.settings.stt_language}

    async def transcribe_upload(self, audio_file: UploadFile) -> dict[str, Any]:
        if not self.settings.stt_enabled:
            raise HTTPException(status_code=503, detail="Speech-to-text is disabled")

        suffix = os.path.splitext(audio_file.filename or "audio.webm")[1] or ".webm"
        raw_audio = await audio_file.read()
        if not raw_audio:
            raise HTTPException(status_code=400, detail="Uploaded audio file is empty")

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(raw_audio)
                temp_path = temp_file.name

            transcript = await asyncio.to_thread(self._transcribe_sync, temp_path)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Speech transcription failed: {exc}",
            ) from exc
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

        if not transcript.get("text"):
            raise HTTPException(status_code=422, detail="No speech was detected in the audio")

        return transcript

    async def preload(self) -> None:
        await asyncio.to_thread(self._load_model)


@lru_cache()
def get_stt_service() -> QwenSTTService:
    return QwenSTTService(get_settings())