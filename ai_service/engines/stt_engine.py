"""
STT Engine — wraps Faster-Whisper for local speech-to-text transcription.
Supports WAV, MP3, M4A. Returns transcript + detected language.
"""
import io
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class STTEngine:
    def __init__(self, model):
        self.model = model  # WhisperModel instance from loader

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> dict:
        """
        Transcribe audio bytes to text.
        Returns {"transcript": str, "language_detected": str}
        """
        if self.model is None:
            logger.error("STT model not loaded")
            return {"transcript": "", "language_detected": "unknown"}

        start = time.time()
        try:
            audio_stream = io.BytesIO(audio_bytes)
            segments, info = self.model.transcribe(
                audio_stream,
                beam_size=5,
                language=None,  # auto-detect; supports Hindi, English, Hinglish
                vad_filter=True,  # skip silent segments
            )
            transcript = " ".join(seg.text.strip() for seg in segments).strip()
            language = info.language if info.language else "unknown"
            elapsed = round((time.time() - start) * 1000)
            logger.info(f"STT completed in {elapsed}ms, language={language}, chars={len(transcript)}")
            return {"transcript": transcript, "language_detected": language}
        except Exception as e:
            logger.error(f"STT transcription failed: {e}")
            return {"transcript": "", "language_detected": "unknown"}
