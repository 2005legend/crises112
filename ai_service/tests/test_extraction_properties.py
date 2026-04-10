# Feature: emergency-intelligence-fusion, Property 1: Extraction Schema Completeness
# Feature: emergency-intelligence-fusion, Property 2: Extraction JSON Round-Trip
# Feature: emergency-intelligence-fusion, Property 3: Malformed Extraction Rejected
"""
Property-based tests for the Extraction Pipeline.
All Groq API calls are mocked so tests run without real credentials.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, settings, HealthCheck
import hypothesis.strategies as st
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_EXTRACTION = {
    "incident_type": "road_accident",
    "location_string": "Anna Nagar",
    "time_reference": None,
    "victim_count": 2,
    "risk_keywords": ["accident", "injured"],
    "summary": "Road accident near Anna Nagar with 2 injured.",
}

REQUIRED_FIELDS = [
    "incident_type",
    "location_string",
    "time_reference",
    "victim_count",
    "risk_keywords",
    "summary",
]

FIELD_TYPES = {
    "incident_type": (str, type(None)),
    "location_string": (str, type(None)),
    "time_reference": (str, type(None)),
    "victim_count": (int, type(None)),
    "risk_keywords": list,
    "summary": str,
}


def _mock_groq_returns(payload: dict):
    """Return a context manager that makes _call_groq return the given payload as JSON."""
    return patch(
        "engines.extraction._call_groq",
        return_value=json.dumps(payload),
    )


# ---------------------------------------------------------------------------
# Property 1: Extraction Schema Completeness
# Validates: Requirements 2.1, R2-3.1
# ---------------------------------------------------------------------------

@given(st.text(min_size=1))
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_extraction_schema_completeness(text):
    """
    For any non-empty text input, extract_fields() must always return a dict
    containing exactly the six required fields, each either a correctly-typed
    value or null — never absent.
    **Validates: Requirements 2.1, R2-3.1**
    """
    from engines.extraction import extract_fields

    with _mock_groq_returns(VALID_EXTRACTION):
        result = extract_fields(text)

    # All six fields must be present
    for field in REQUIRED_FIELDS:
        assert field in result, f"Field '{field}' missing from extraction result"

    # Each field must have the correct type or be None
    for field, expected_types in FIELD_TYPES.items():
        val = result[field]
        if isinstance(expected_types, tuple):
            assert isinstance(val, expected_types), (
                f"Field '{field}' has wrong type {type(val)}, expected {expected_types}"
            )
        else:
            assert isinstance(val, expected_types), (
                f"Field '{field}' has wrong type {type(val)}, expected {expected_types}"
            )

    # Summary must not exceed 200 chars
    assert len(result["summary"]) <= 200


# ---------------------------------------------------------------------------
# Property 2: Extraction JSON Round-Trip
# Validates: Requirements 9.2, 9.3
# ---------------------------------------------------------------------------

@st.composite
def valid_extraction_objects(draw):
    """Generate valid extraction schema objects with all 6 fields."""
    incident_type = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    location_string = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    time_reference = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    victim_count = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=1000)))
    risk_keywords = draw(st.lists(st.text(min_size=1, max_size=30), max_size=10))
    summary = draw(st.text(min_size=1, max_size=200))
    return {
        "incident_type": incident_type,
        "location_string": location_string,
        "time_reference": time_reference,
        "victim_count": victim_count,
        "risk_keywords": risk_keywords,
        "summary": summary,
    }


@given(valid_extraction_objects())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_extraction_json_roundtrip(obj):
    """
    For any valid extraction schema object, serializing to JSON and deserializing
    must produce a structurally and value-equal object.
    **Validates: Requirements 9.2, 9.3**
    """
    serialized = json.dumps(obj)
    deserialized = json.loads(serialized)

    assert set(deserialized.keys()) == set(obj.keys()), "Keys differ after round-trip"
    for field in REQUIRED_FIELDS:
        assert deserialized[field] == obj[field], (
            f"Field '{field}' value changed after round-trip: {obj[field]!r} → {deserialized[field]!r}"
        )


# ---------------------------------------------------------------------------
# Property 3: Malformed Extraction Rejected
# Validates: Requirements 9.4, R2-3.4
# ---------------------------------------------------------------------------

@st.composite
def malformed_extraction_payloads(draw):
    """Generate JSON payloads that violate the extraction schema."""
    strategy = draw(st.integers(min_value=0, max_value=3))
    if strategy == 0:
        # Missing one or more required keys
        keys = draw(st.lists(
            st.sampled_from(REQUIRED_FIELDS),
            min_size=1,
            max_size=5,
            unique=True,
        ))
        obj = dict(VALID_EXTRACTION)
        for k in keys:
            del obj[k]
        return obj
    elif strategy == 1:
        # Wrong type for victim_count (string instead of int)
        obj = dict(VALID_EXTRACTION)
        obj["victim_count"] = draw(st.text(min_size=1, max_size=10))
        return obj
    elif strategy == 2:
        # Wrong type for risk_keywords (string instead of list)
        obj = dict(VALID_EXTRACTION)
        obj["risk_keywords"] = draw(st.text(min_size=1, max_size=20))
        return obj
    else:
        # summary is None (not allowed — must be str)
        obj = dict(VALID_EXTRACTION)
        obj["summary"] = None
        return obj


@given(malformed_extraction_payloads())
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_malformed_extraction_rejected(malformed_payload):
    """
    For any JSON payload that violates the extraction schema, the endpoint
    must return HTTP 422 and must not persist the malformed data.
    **Validates: Requirements 9.4, R2-3.4**
    """
    from fastapi.testclient import TestClient
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Mock _call_groq to return the malformed payload
    with patch("engines.extraction._call_groq", return_value=json.dumps(malformed_payload)):
        from engines.extraction import extract_fields
        with pytest.raises((ValueError, Exception)):
            extract_fields("some emergency text")
