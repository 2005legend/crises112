"""
POST /stt — Faster-Whisper speech-to-text endpoint.
Accepts WAV, MP3, M4A audio files. Returns transcript + detected language.
"""
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from pydantic import BaseModel
from ai_service.engines.stt_engine import STTEngine

router = APIRouter()

ALLOWED_AUDIO_TYPES = {"audio/wav", "audio/mpeg", "audio/mp4", "audio/x-m4a", "audio/mp3", "application/octet-stream"}
MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50 MB


class STTResponse(BaseModel):
    transcript: str
    language_detected: str


@router.post("", response_model=STTResponse, summary="Transcribe audio to text")
async def transcribe(request: Request, file: UploadFile = File(...)):
    """
    Transcribe a voice audio file (WAV, MP3, M4A) to text using Faster-Whisper.
    Returns transcript and detected language. Returns empty transcript for silent audio.
    """
    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_SIZE:
        raise HTTPException(status_code=413, detail="Audio file exceeds 50 MB limit")

    models = request.app.state.models
    if models.stt_model is None:
        raise HTTPException(status_code=503, detail="STT model not loaded")

    engine = STTEngine(models.stt_model)
    result = engine.transcribe(audio_bytes, filename=file.filename or "audio.wav")
    return STTResponse(**result)
