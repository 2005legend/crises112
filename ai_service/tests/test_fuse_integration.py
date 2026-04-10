"""
Integration tests for the full fuse pipeline — each modality.
Uses FastAPI TestClient with mocked external API calls.
"""
import io
import json
import wave
import struct
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


VALID_EXTRACTION = {
    "incident_type": "road_accident",
    "location_string": "Anna Nagar",
    "time_reference": None,
    "victim_count": 2,
    "risk_keywords": ["accident", "injured"],
    "summary": "Road accident near Anna Nagar with 2 injured.",
}

REQUIRED_EXTRACTION_FIELDS = [
    "incident_type",
    "location_string",
    "time_reference",
    "victim_count",
    "risk_keywords",
    "summary",
]


def make_tiny_wav() -> bytes:
    """Generate a minimal valid WAV file programmatically."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # 0.1 seconds of silence
        frames = struct.pack("<" + "h" * 1600, *([0] * 1600))
        wf.writeframes(frames)
    return buf.getvalue()


def make_tiny_jpeg() -> bytes:
    """Return a minimal 1x1 pixel JPEG."""
    # Minimal valid JPEG bytes (1x1 white pixel)
    return bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
        0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
        0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
        0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
        0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
        0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
        0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
        0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
        0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
        0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
        0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
        0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
        0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
        0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
        0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD2, 0x8A, 0x28, 0x03, 0xFF, 0xD9,
    ])


@pytest.fixture
def client():
    with patch("engines.extraction._call_groq", return_value=json.dumps(VALID_EXTRACTION)):
        from main import app
        with TestClient(app) as c:
            yield c


class TestFuseTextModality:
    def test_text_modality_returns_extracted_fields(self, client):
        """
        POST /ai/fuse-report with modality=text should return extracted with all 6 fields
        and errors should be empty.
        """
        response = client.post(
            "/ai/fuse-report",
            data={
                "modality": "text",
                "text": "Fire near Anna Nagar signal, 2 people injured.",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["errors"] == []
        assert body["extracted"] is not None
        for field in REQUIRED_EXTRACTION_FIELDS:
            assert field in body["extracted"], f"Missing field: {field}"

    def test_text_modality_transcript_is_null(self, client):
        """Text modality should have transcript=null."""
        response = client.post(
            "/ai/fuse-report",
            data={"modality": "text", "text": "Some emergency text."},
        )
        assert response.status_code == 200
        assert response.json()["transcript"] is None

    def test_text_modality_caption_is_null(self, client):
        """Text modality should have caption=null."""
        response = client.post(
            "/ai/fuse-report",
            data={"modality": "text", "text": "Some emergency text."},
        )
        assert response.status_code == 200
        assert response.json()["caption"] is None


class TestFuseVoiceModality:
    def test_voice_modality_transcript_present(self):
        """POST /ai/fuse-report with modality=voice should return transcript field."""
        mock_model = MagicMock()
        mock_info = MagicMock()
        mock_info.language = "en"
        seg = MagicMock()
        seg.text = "Fire near Anna Nagar."
        mock_model.transcribe.return_value = ([seg], mock_info)

        with patch("engines.stt.get_whisper", return_value=mock_model), \
             patch("engines.extraction._call_groq", return_value=json.dumps(VALID_EXTRACTION)):
            from main import app
            client = TestClient(app)
            wav_bytes = make_tiny_wav()
            response = client.post(
                "/ai/fuse-report",
                data={"modality": "voice"},
                files={"file": ("test.wav", wav_bytes, "audio/wav")},
            )

        assert response.status_code == 200
        body = response.json()
        assert "transcript" in body
        assert body["transcript"] is not None

    def test_voice_modality_missing_file_adds_error(self):
        """Voice modality without file should add an error but not crash."""
        with patch("engines.extraction._call_groq", return_value=json.dumps(VALID_EXTRACTION)):
            from main import app
            client = TestClient(app)
            response = client.post(
                "/ai/fuse-report",
                data={"modality": "voice"},
            )

        assert response.status_code == 200
        body = response.json()
        assert len(body["errors"]) > 0


class TestFuseImageModality:
    def test_image_modality_caption_present(self):
        """POST /ai/fuse-report with modality=image should return caption field."""
        mock_vision_response = {
            "message": {"content": "Two vehicles collided.---ENTITIES---vehicle, person"}
        }
        with patch("ollama.chat", return_value=mock_vision_response), \
             patch("engines.extraction._call_groq", return_value=json.dumps(VALID_EXTRACTION)):
            from main import app
            client = TestClient(app)
            jpeg_bytes = make_tiny_jpeg()
            response = client.post(
                "/ai/fuse-report",
                data={"modality": "image"},
                files={"file": ("test.jpg", jpeg_bytes, "image/jpeg")},
            )

        assert response.status_code == 200
        body = response.json()
        assert "caption" in body
        assert body["caption"] is not None

    def test_image_modality_missing_file_adds_error(self):
        """Image modality without file should add an error but not crash."""
        with patch("engines.extraction._call_groq", return_value=json.dumps(VALID_EXTRACTION)):
            from main import app
            client = TestClient(app)
            response = client.post(
                "/ai/fuse-report",
                data={"modality": "image"},
            )

        assert response.status_code == 200
        body = response.json()
        assert len(body["errors"]) > 0


class TestFuseErrorHandling:
    def test_unknown_modality_adds_error_no_500(self):
        """Unknown modality should add error but return 200, not 500."""
        with patch("engines.extraction._call_groq", return_value=json.dumps(VALID_EXTRACTION)):
            from main import app
            client = TestClient(app)
            response = client.post(
                "/ai/fuse-report",
                data={"modality": "unknown_modality", "text": "some text"},
            )

        assert response.status_code == 200
        body = response.json()
        assert any("unknown modality" in e for e in body["errors"])

    def test_extraction_failure_adds_error_no_500(self):
        """Extraction failure should add error but return 200 with partial results."""
        with patch("engines.extraction._call_groq", return_value="not valid json"):
            from main import app
            client = TestClient(app)
            response = client.post(
                "/ai/fuse-report",
                data={"modality": "text", "text": "some emergency text"},
            )

        assert response.status_code == 200
        body = response.json()
        assert len(body["errors"]) > 0
        assert body["extracted"] is None
