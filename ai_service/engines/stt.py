"""
STT Engine — Faster-Whisper transcription.
Supports WAV, MP3, M4A. Returns empty transcript for silent/unintelligible audio.
"""
import io
import logging
import tempfile
import os
from engines.loader import get_whisper
from engines.utils import log_latency
import time

logger = logging.getLogger(__name__)


def transcribe(audio_bytes: bytes, filename: str) -> dict:
    """
    Transcribe audio bytes using Faster-Whisper.

    Returns:
        {"transcript": str, "language_detected": str}
    Never raises — returns empty transcript on failure.
    """
    start = time.perf_counter()
    model = get_whisper()

    if model is None:
        logger.error("Whisper model not loaded.")
        return {"transcript": "", "language_detected": "unknown"}

    # Determine file extension for temp file
    ext = os.path.splitext(filename)[-1].lower() or ".wav"
    if ext not in (".wav", ".mp3", ".m4a"):
        ext = ".wav"

    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        segments, info = model.transcribe(tmp_path, beam_size=5)
        transcript_parts = [seg.text for seg in segments]
        transcript = " ".join(transcript_parts).strip()
        language = info.language if info.language else "unknown"

        log_latency("stt", start)
        return {"transcript": transcript, "language_detected": language}

    except Exception as exc:
        logger.error("STT transcription failed: %s", exc)
        return {"transcript": "", "language_detected": "unknown"}
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
