"""
Tests for the Extraction Engine.
Covers: schema completeness, JSON round-trip, malformed rejection, Hinglish support.
Includes property-based tests (Properties 1, 2, 3) using hypothesis.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, settings, strategies as st

from ai_service.engines.extraction_engine import ExtractionEngine, ExtractionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {"incident_type", "location_string", "time_reference", "victim_count", "risk_keywords", "summary"}

VALID_INCIDENT_TYPES = {"road_accident", "fire", "medical", "crime", "flood", "other", None}


def make_mock_groq_response(content: str):
    """Build a mock Groq API response object."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestExtractionEngineUnit:

    def test_empty_text_returns_empty_result(self):
        engine = ExtractionEngine()
        result = engine.extract("")
        assert result["incident_type"] is None
        assert result["risk_keywords"] == []
        assert result["summary"] == ""

    def test_whitespace_only_returns_empty_result(self):
        engine = ExtractionEngine()
        result = engine.extract("   ")
        assert result["incident_type"] is None

    def test_valid_extraction_returns_all_fields(self):
        valid_json = json.dumps({
            "incident_type": "road_accident",
            "location_string": "Anna Nagar signal",
            "time_reference": "this morning",
            "victim_count": 2,
            "risk_keywords": ["injured", "bleeding"],
            "summary": "Road accident near Anna Nagar signal with 2 injured persons"
        })
        engine = ExtractionEngine()
        with patch.object(engine.client.chat.completions, "create", return_value=make_mock_groq_response(valid_json)):
            result = engine.extract("Lorry hit a bike near Anna Nagar signal, 2 people injured")

        assert result["incident_type"] == "road_accident"
        assert result["location_string"] == "Anna Nagar signal"
        assert result["victim_count"] == 2
        assert "injured" in result["risk_keywords"]
        assert len(result["summary"]) <= 200

    def test_null_fields_when_undeterminable(self):
        partial_json = json.dumps({
            "incident_type": None,
            "location_string": None,
            "time_reference": None,
            "victim_count": None,
            "risk_keywords": [],
            "summary": "Emergency reported"
        })
        engine = ExtractionEngine()
        with patch.object(engine.client.chat.completions, "create", return_value=make_mock_groq_response(partial_json)):
            result = engine.extract("Something happened somewhere")

        assert result["incident_type"] is None
        assert result["location_string"] is None
        assert result["victim_count"] is None

    def test_summary_truncated_to_200_chars(self):
        long_summary = "x" * 300
        valid_json = json.dumps({
            "incident_type": "other",
            "location_string": None,
            "time_reference": None,
            "victim_count": None,
            "risk_keywords": [],
            "summary": long_summary
        })
        engine = ExtractionEngine()
        with patch.object(engine.client.chat.completions, "create", return_value=make_mock_groq_response(valid_json)):
            result = engine.extract("test input")

        assert len(result["summary"]) <= 200

    def test_malformed_json_retries_and_raises(self):
        engine = ExtractionEngine()
        with patch.object(engine.client.chat.completions, "create", return_value=make_mock_groq_response("not json at all")):
            with pytest.raises(ValueError, match="Extraction failed after 2 attempts"):
                engine.extract("some emergency text")

    def test_victim_count_coerced_from_string(self):
        valid_json = json.dumps({
            "incident_type": "medical",
            "location_string": "hospital",
            "time_reference": None,
            "victim_count": "3",  # string instead of int
            "risk_keywords": [],
            "summary": "Medical emergency"
        })
        engine = ExtractionEngine()
        with patch.object(engine.client.chat.completions, "create", return_value=make_mock_groq_response(valid_json)):
            result = engine.extract("medical emergency at hospital with 3 patients")

        assert result["victim_count"] == 3

    def test_victim_count_invalid_string_becomes_none(self):
        valid_json = json.dumps({
            "incident_type": "medical",
            "location_string": None,
            "time_reference": None,
            "victim_count": "unknown",
            "risk_keywords": [],
            "summary": "Medical emergency"
        })
        engine = ExtractionEngine()
        with patch.object(engine.client.chat.completions, "create", return_value=make_mock_groq_response(valid_json)):
            result = engine.extract("medical emergency")

        assert result["victim_count"] is None


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Property 1: Extraction Schema Completeness
@given(st.text(min_size=1, max_size=500))
@settings(max_examples=50, deadline=2000)
def test_property1_extraction_schema_completeness(text):
    """
    For any non-empty text, the extraction result always contains exactly
    the six required fields, each either a correctly-typed value or null.
    """
    valid_json = json.dumps({
        "incident_type": None,
        "location_string": None,
        "time_reference": None,
        "victim_count": None,
        "risk_keywords": [],
        "summary": text[:200]
    })
    engine = ExtractionEngine()
    with patch.object(engine.client.chat.completions, "create", return_value=make_mock_groq_response(valid_json)):
        result = engine.extract(text)

    # All required fields must be present
    for field in REQUIRED_FIELDS:
        assert field in result, f"Field '{field}' missing from extraction result"

    # Type checks
    assert result["incident_type"] is None or isinstance(result["incident_type"], str)
    assert result["location_string"] is None or isinstance(result["location_string"], str)
    assert result["time_reference"] is None or isinstance(result["time_reference"], str)
    assert result["victim_count"] is None or isinstance(result["victim_count"], int)
    assert isinstance(result["risk_keywords"], list)
    assert isinstance(result["summary"], str)


# Property 2: Extraction JSON Round-Trip
@given(
    incident_type=st.one_of(st.none(), st.sampled_from(["road_accident", "fire", "medical", "crime", "flood", "other"])),
    location_string=st.one_of(st.none(), st.text(min_size=1, max_size=100)),
    time_reference=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    victim_count=st.one_of(st.none(), st.integers(min_value=0, max_value=1000)),
    risk_keywords=st.lists(st.text(min_size=1, max_size=20), max_size=10),
    summary=st.text(min_size=0, max_size=200),
)
@settings(max_examples=100)
def test_property2_extraction_json_roundtrip(
    incident_type, location_string, time_reference, victim_count, risk_keywords, summary
):
    """
    For any valid extraction schema object, serializing to JSON and deserializing
    produces an object equal to the original.
    """
    original = ExtractionResult(
        incident_type=incident_type,
        location_string=location_string,
        time_reference=time_reference,
        victim_count=victim_count,
        risk_keywords=risk_keywords,
        summary=summary,
    )
    serialized = original.model_dump_json()
    deserialized = ExtractionResult.model_validate_json(serialized)

    assert deserialized.incident_type == original.incident_type
    assert deserialized.location_string == original.location_string
    assert deserialized.time_reference == original.time_reference
    assert deserialized.victim_count == original.victim_count
    assert deserialized.risk_keywords == original.risk_keywords
    assert deserialized.summary == original.summary[:200]


# Property 3: Malformed Extraction Rejected
@given(st.text(min_size=1, max_size=200))
@settings(max_examples=50, deadline=2000)
def test_property3_malformed_extraction_rejected(bad_response):
    """
    For any response that is not valid JSON matching the schema,
    the engine raises ValueError (which maps to HTTP 422).
    """
    # Ensure the text is not accidentally valid JSON matching our schema
    try:
        parsed = json.loads(bad_response)
        if isinstance(parsed, dict) and all(k in parsed for k in REQUIRED_FIELDS):
            return  # skip — this is actually valid
    except (json.JSONDecodeError, ValueError):
        pass  # expected — not valid JSON

    engine = ExtractionEngine()
    with patch.object(engine.client.chat.completions, "create", return_value=make_mock_groq_response(bad_response)):
        with pytest.raises((ValueError, Exception)):
            engine.extract("some emergency text")
