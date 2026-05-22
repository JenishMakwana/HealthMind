from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from loguru import logger

from app.core.config import get_settings
from app.core.security import get_current_user_id
from app.schemas.schemas import SpeechToTextResponse
from app.services.speech_service import get_speech_service

router = APIRouter(prefix="/audio", tags=["audio"])

ALLOWED_AUDIO_EXTENSIONS = {"wav", "mp3", "m4a", "mp4", "webm", "ogg", "flac", "opus"}


def _validate_audio_file(filename: str, size_bytes: int) -> None:
    settings = get_settings()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format. Allowed: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}",
        )
    max_bytes = settings.speech_max_upload_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio file is too large. Maximum size is {settings.speech_max_upload_mb} MB.",
        )


@router.post("/transcribe", response_model=SpeechToTextResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    _: str = Depends(get_current_user_id),
):
    filename = file.filename or "recording.wav"
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audio file is empty")

    _validate_audio_file(filename, len(raw_bytes))
    suffix = Path(filename).suffix or ".wav"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(raw_bytes)
            temp_path = temp_file.name
        text = get_speech_service().transcribe(temp_path)
    except Exception as exc:
        logger.exception("STT transcription failed for {}", filename)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

    if not text.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No speech was detected in the recording")

    return SpeechToTextResponse(
        text=text.strip(),
        language=None,
        model=get_settings().stt_model,
        filename=filename,
    )


