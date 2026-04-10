"""
Tests for the STT Engine.
Covers: silent audio, valid audio, error handling, language detection.
"""
import pytest
from unittest.mock import MagicMock, patch
from ai_service.engines.stt_engine import STTEngine


def make_mock_whisper(segments_text: list[str], language: str = "en"):
    """Build a mock WhisperModel that returns given segments."""
    model = MagicMock()
    segments = [MagicMock(text=t) for t in segments_text]
    info = MagicMock()
    info.language = language
    model.transcribe.return_value = (iter(segments), info)
    return model


class TestSTTEngine:
    def test_valid_audio_returns_transcript(self):
        model = make_mock_whisper(["Lorry hit a bike ", "near Anna Nagar signal."], language="en")
        engine = STTEngine(model)
        result = engine.transcribe(b"fake_audio_bytes")
        assert result["transcript"] == "Lorry hit a bike near Anna Nagar signal."
        assert result["language_detected"] == "en"

    def test_silent_audio_returns_empty_transcript(self):
        """VAD filter removes silent segments — empty transcript, no error."""
        model = make_mock_whisper([], language="unknown")
        engine = STTEngine(model)
        result = engine.transcribe(b"silent_audio")
        assert result["transcript"] == ""
        assert result["language_detected"] == "unknown"

    def test_hindi_audio_detected(self):
        model = make_mock_whisper(["Yahan ek accident hua hai"], language="hi")
        engine = STTEngine(model)
        result = engine.transcribe(b"hindi_audio")
        assert result["language_detected"] == "hi"
        assert "accident" in result["transcript"]

    def test_model_none_returns_empty(self):
        engine = STTEngine(model=None)
        result = engine.transcribe(b"some_audio")
        assert result["transcript"] == ""
        assert result["language_detected"] == "unknown"

    def test_transcription_exception_returns_empty(self):
        model = MagicMock()
        model.transcribe.side_effect = RuntimeError("model error")
        engine = STTEngine(model)
        result = engine.transcribe(b"bad_audio")
        assert result["transcript"] == ""
        assert result["language_detected"] == "unknown"

    def test_multiple_segments_joined(self):
        model = make_mock_whisper(["First part.", " Second part.", " Third part."])
        engine = STTEngine(model)
        result = engine.transcribe(b"audio")
        assert "First part." in result["transcript"]
        assert "Second part." in result["transcript"]
        assert "Third part." in result["transcript"]
