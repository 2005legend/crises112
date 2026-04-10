"""
Unit tests for each AI engine in isolation.
All external API calls (Faster-Whisper, ollama, Groq) are mocked.
"""
import json
import numpy as np
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# STT Engine Tests
# ---------------------------------------------------------------------------

class TestSTTEngine:
    def test_silent_audio_returns_empty_transcript(self):
        """Silent audio should return empty transcript, not raise."""
        mock_model = MagicMock()
        mock_info = MagicMock()
        mock_info.language = "unknown"
        mock_model.transcribe.return_value = ([], mock_info)

        with patch("engines.stt.get_whisper", return_value=mock_model):
            from engines.stt import transcribe
            result = transcribe(b"\x00" * 1000, "silent.wav")

        assert result["transcript"] == ""
        assert result["language_detected"] == "unknown"

    def test_valid_audio_returns_nonempty_transcript(self):
        """Valid audio bytes should produce a non-empty transcript."""
        mock_model = MagicMock()
        mock_info = MagicMock()
        mock_info.language = "en"

        seg1 = MagicMock()
        seg1.text = "There is a fire near Anna Nagar."
        mock_model.transcribe.return_value = ([seg1], mock_info)

        with patch("engines.stt.get_whisper", return_value=mock_model):
            from engines.stt import transcribe
            result = transcribe(b"fake_wav_bytes", "test.wav")

        assert result["transcript"] == "There is a fire near Anna Nagar."
        assert result["language_detected"] == "en"

    def test_model_not_loaded_returns_empty(self):
        """If whisper model is None, return empty transcript gracefully."""
        with patch("engines.stt.get_whisper", return_value=None):
            from engines.stt import transcribe
            result = transcribe(b"bytes", "audio.wav")

        assert result["transcript"] == ""
        assert result["language_detected"] == "unknown"

    def test_transcription_exception_returns_empty(self):
        """If transcription raises, return empty transcript gracefully."""
        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("model error")

        with patch("engines.stt.get_whisper", return_value=mock_model):
            from engines.stt import transcribe
            result = transcribe(b"bytes", "audio.wav")

        assert result["transcript"] == ""
        assert result["language_detected"] == "unknown"


# ---------------------------------------------------------------------------
# Vision Engine Tests
# ---------------------------------------------------------------------------

class TestVisionEngine:
    def test_non_emergency_image_returns_neutral_caption(self):
        """Non-emergency image should return a neutral caption without fabricated details."""
        mock_response = {
            "message": {
                "content": "This image shows a clear blue sky with no visible emergency content.---ENTITIES---sky, clouds"
            }
        }
        with patch("ollama.chat", return_value=mock_response):
            from engines.vision import caption_image
            result = caption_image(b"fake_image_bytes", "sky.jpg")

        assert "emergency" not in result["caption"].lower() or "no" in result["caption"].lower()
        assert isinstance(result["entities"], list)

    def test_ollama_unavailable_returns_fallback(self):
        """If ollama is unavailable, return a graceful fallback response."""
        with patch("ollama.chat", side_effect=Exception("connection refused")):
            from engines.vision import caption_image
            result = caption_image(b"fake_image_bytes", "image.jpg")

        assert result["caption"] != ""
        assert "unavailable" in result["caption"].lower() or "vision" in result["caption"].lower()
        assert isinstance(result["entities"], list)

    def test_caption_with_entities_parsed_correctly(self):
        """Caption and entities should be parsed from the separator format."""
        mock_response = {
            "message": {
                "content": "Two vehicles collided, one person injured.---ENTITIES---vehicle, person, injury"
            }
        }
        with patch("ollama.chat", return_value=mock_response):
            from engines.vision import caption_image
            result = caption_image(b"fake_image_bytes", "accident.jpg")

        assert result["caption"] == "Two vehicles collided, one person injured."
        assert "vehicle" in result["entities"]
        assert "person" in result["entities"]


# ---------------------------------------------------------------------------
# Extraction Engine Tests
# ---------------------------------------------------------------------------

class TestExtractionEngine:
    VALID_RESPONSE = {
        "incident_type": "road_accident",
        "location_string": "Anna Nagar",
        "time_reference": None,
        "victim_count": 2,
        "risk_keywords": ["accident", "injured"],
        "summary": "Road accident near Anna Nagar with 2 injured.",
    }

    def test_hinglish_input_returns_valid_schema(self):
        """Hinglish input should return a valid extraction schema."""
        with patch("engines.extraction._call_groq", return_value=json.dumps(self.VALID_RESPONSE)):
            from engines.extraction import extract_fields
            result = extract_fields("Anna Nagar ke paas accident hua, 2 log ghaayal hain")

        assert "incident_type" in result
        assert "location_string" in result
        assert "time_reference" in result
        assert "victim_count" in result
        assert "risk_keywords" in result
        assert "summary" in result

    def test_ambiguous_input_returns_null_fields(self):
        """Ambiguous input should return null for undeterminable fields."""
        ambiguous_response = {
            "incident_type": None,
            "location_string": None,
            "time_reference": None,
            "victim_count": None,
            "risk_keywords": [],
            "summary": "Unclear report with no specific details.",
        }
        with patch("engines.extraction._call_groq", return_value=json.dumps(ambiguous_response)):
            from engines.extraction import extract_fields
            result = extract_fields("something happened somewhere")

        assert result["incident_type"] is None
        assert result["location_string"] is None
        assert result["victim_count"] is None

    def test_malformed_model_response_raises_value_error(self):
        """Malformed model response should raise ValueError after retry."""
        with patch("engines.extraction._call_groq", return_value="not valid json at all"):
            from engines.extraction import extract_fields
            with pytest.raises(ValueError):
                extract_fields("some text")

    def test_missing_field_raises_value_error(self):
        """Response missing a required field should raise ValueError."""
        incomplete = {"incident_type": "fire", "summary": "Fire reported."}
        with patch("engines.extraction._call_groq", return_value=json.dumps(incomplete)):
            from engines.extraction import extract_fields
            with pytest.raises(ValueError):
                extract_fields("fire near station")

    def test_summary_truncated_to_200_chars(self):
        """Summary longer than 200 chars should be truncated."""
        long_response = dict(self.VALID_RESPONSE)
        long_response["summary"] = "A" * 300
        with patch("engines.extraction._call_groq", return_value=json.dumps(long_response)):
            from engines.extraction import extract_fields
            result = extract_fields("some text")

        assert len(result["summary"]) <= 200


# ---------------------------------------------------------------------------
# Dedup Engine Tests
# ---------------------------------------------------------------------------

class TestDedupEngine:
    def test_boundary_075_no_merge(self):
        """Similarity exactly 0.75 must NOT trigger a merge."""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.75, np.sqrt(1 - 0.75**2), 0.0])

        with patch("engines.dedup.get_embedding") as mock_emb:
            mock_emb.side_effect = [a, b]
            from engines.dedup import find_match
            result = find_match("text_a", [{"incident_id": "test-001", "summary": "text_b"}])

        assert result["match"] is None

    def test_above_075_triggers_merge(self):
        """Similarity 0.76 must trigger a merge."""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.76, np.sqrt(1 - 0.76**2), 0.0])

        with patch("engines.dedup.get_embedding") as mock_emb:
            mock_emb.side_effect = [a, b]
            from engines.dedup import find_match
            result = find_match("text_a", [{"incident_id": "test-001", "summary": "text_b"}])

        assert result["match"] == "test-001"

    def test_empty_candidates_returns_null(self):
        """Empty candidates list should return match=null."""
        from engines.dedup import find_match
        result = find_match("some summary", [])
        assert result["match"] is None
        assert result["similarity_score"] == 0.0

    def test_merge_reason_contains_incident_id_and_score(self):
        """merge_reason must include incident ID and score when matched."""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.9, np.sqrt(1 - 0.9**2), 0.0])

        with patch("engines.dedup.get_embedding") as mock_emb:
            mock_emb.side_effect = [a, b]
            from engines.dedup import find_match
            result = find_match("text_a", [{"incident_id": "INC-42", "summary": "text_b"}])

        assert "INC-42" in result["merge_reason"]
        assert str(round(result["similarity_score"], 2)) in result["merge_reason"] or \
               "0.9" in result["merge_reason"]
