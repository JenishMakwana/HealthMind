import os

import torch
from loguru import logger
from qwen_asr import Qwen3ASRModel


class SpeechService:
    def __init__(self, model_name: str = "Qwen/Qwen3-ASR-0.6B", device: str = None):
        """
        Initializes the Qwen-ASR model for speech-to-text.
        """
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info(f"Initializing SpeechService with model {model_name} on {self.device}")

        try:
            dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
            self.model = Qwen3ASRModel.from_pretrained(
                model_name,
                dtype=dtype,
                device_map=self.device if self.device == "cuda" else None,
            )
            logger.success("SpeechService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize SpeechService: {e}")
            raise

    def transcribe(self, audio_data, language: str = None) -> str:
        """
        Transcribes audio (file path or numpy array) to text.
        """
        import tempfile

        import numpy as np
        import soundfile as sf

        temp_file = None
        try:
            if isinstance(audio_data, str):
                if not os.path.exists(audio_data):
                    logger.error(f"Audio file not found: {audio_data}")
                    raise FileNotFoundError(f"Audio file not found: {audio_data}")
                logger.info(f"Transcribing audio file: {audio_data}")
                input_audio = [audio_data]
            elif isinstance(audio_data, np.ndarray):
                logger.info("Transcribing audio buffer (NumPy array)")
                temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                sf.write(temp_file.name, audio_data, 16000)
                temp_file.close()
                input_audio = [temp_file.name]
            else:
                input_audio = audio_data

            results = self.model.transcribe(
                audio=input_audio,
                language=[language] if language else None,
            )

            if results and len(results) > 0:
                transcription = results[0].text
                logger.info(f"Transcription successful: {transcription[:50]}...")
                return transcription

            logger.warning("No transcription results returned")
            return ""
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            raise
        finally:
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except Exception as cleanup_err:
                    logger.warning(f"Failed to delete temp file {temp_file.name}: {cleanup_err}")

    def record_and_transcribe(self, duration: int = 5, sample_rate: int = 16000) -> str:
        """
        Records audio from the microphone for a fixed duration and transcribes it.
        """
        import sounddevice as sd

        logger.info(f"Recording for {duration} seconds...")
        recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1)
        sd.wait()

        audio_data = recording.flatten()
        return self.transcribe(audio_data)

    def transcribe_stream(self, callback_fn, chunk_duration: int = 5, sample_rate: int = 16000):
        """
        Captures audio from the microphone and transcribes it in real-time.
        """
        import sounddevice as sd

        logger.info(f"Starting microphone stream ({chunk_duration}s chunks)...")

        def sd_callback(indata, frames, time, status):
            if status:
                logger.warning(f"Sounddevice status: {status}")

            audio_chunk = indata.copy().flatten()
            try:
                text = self.transcribe(audio_chunk)
                if text.strip():
                    callback_fn(text)
            except Exception as e:
                logger.error(f"Error in stream transcription: {e}")

        block_size = int(sample_rate * chunk_duration)

        try:
            with sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                callback=sd_callback,
                blocksize=block_size,
            ):
                logger.info("Microphone is live. Press Ctrl+C to stop.")
                while True:
                    sd.sleep(1000)
        except KeyboardInterrupt:
            logger.info("Microphone stream stopped by user.")
        except Exception as e:
            logger.error(f"Error in microphone stream: {e}")
            raise


speech_service = None


def get_speech_service():
    global speech_service
    if speech_service is None:
        speech_service = SpeechService()
    return speech_service
