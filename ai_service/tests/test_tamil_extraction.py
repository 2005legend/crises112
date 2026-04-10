"""
Tamil-English mixed text extraction test.
Verifies the extraction pipeline does not crash on Tamil input
and returns a valid schema with incident_type detected.

Run: python -m pytest ai_service/tests/test_tamil_extraction.py -v -s -m slow
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from ai_service.engines.extraction_engine import ExtractionEngine

# Tamil-English mixed emergency reports (code-switched)
TAMIL_TEST_CASES = [
    {
        "id": "TM-01",
        "text": "Anna Nagar signal-la oru accident aagiruku, oru payyan kizhe vizhundhan, blood varuthu",
        "description": "Road accident at Anna Nagar signal, boy fell, bleeding",
        "expected_type": "road_accident",
    },
    {
        "id": "TM-02",
        "text": "T Nagar-la oru building-ku thi pidichiruku, smoke varuthu, people odittu varuthaanga",
        "description": "Building fire in T Nagar, smoke visible, people running",
        "expected_type": "fire",
    },
    {
        "id": "TM-03",
        "text": "Koyambedu bus stand-la oru uncle moochu vaangama kizhe vizhundhar, ambulance venum",
        "description": "Old man collapsed at Koyambedu bus stand, needs ambulance",
        "expected_type": "medical",
    },
]


def make_mock_response(incident_type: str, location: str) -> str:
    return json.dumps({
        "incident_type": incident_type,
        "location_string": location,
        "time_reference": None,
        "victim_count": 1,
        "risk_keywords": ["injured"],
        "summary": f"{incident_type} reported near {location}",
        "field_confidence": {"incident_type": 0.85, "location_string": 0.80, "victim_count": 0.70},
    })


class TestTamilExtraction:
    """Tests that Tamil-English mixed text does not crash the pipeline."""

    @pytest.mark.parametrize("case", TAMIL_TEST_CASES, ids=lambda c: c["id"])
    def test_tamil_input_returns_valid_schema(self, case):
        """Tamil-English input must return a valid extraction schema — no crash."""
        mock_response = make_mock_response(case["expected_type"], "test location")
        engine = ExtractionEngine()

        with patch.object(engine.client.chat.completions, "create") as mock_create:
            msg = MagicMock()
            msg.content = mock_response
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            mock_create.return_value = resp

            result = engine.extract(case["text"])

        # Must have all required fields
        for field in ["incident_type", "location_string", "time_reference",
                      "victim_count", "risk_keywords", "summary"]:
            assert field in result, f"Field '{field}' missing for Tamil input {case['id']}"

        # Must not crash — incident_type should be detected
        assert result["incident_type"] == case["expected_type"], (
            f"Expected {case['expected_type']} for {case['id']}, got {result['incident_type']}"
        )

        print(f"\n  [{case['id']}] {case['description']}")
        print(f"  Input   : {case['text'][:80]}...")
        print(f"  Type    : {result['incident_type']}")
        print(f"  Summary : {result['summary']}")


@pytest.mark.slow
class TestTamilExtractionLive:
    """Live test — calls real Groq API with Tamil input."""

    @pytest.mark.parametrize("case", TAMIL_TEST_CASES, ids=lambda c: c["id"])
    def test_tamil_live_extraction(self, case):
        """
        Send real Tamil-English text to Groq and verify:
        1. No crash
        2. Returns valid JSON schema
        3. incident_type is not null (model understands the emergency)
        """
        import os
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            pytest.skip("GROQ_API_KEY not set")

        engine = ExtractionEngine(api_key=api_key)
        result = engine.extract(case["text"])

        print(f"\n  [{case['id']}] {case['description']}")
        print(f"  Input     : {case['text']}")
        print(f"  Type      : {result['incident_type']}")
        print(f"  Location  : {result['location_string']}")
        print(f"  Keywords  : {result['risk_keywords']}")
        print(f"  Summary   : {result['summary']}")
        print(f"  Confidence: {result['field_confidence']}")
        print(f"  Review    : {result['review_flag']} — {result['review_reason']}")

        # Must not crash and must return valid schema
        for field in ["incident_type", "location_string", "risk_keywords", "summary"]:
            assert field in result

        # incident_type should be detected (not null) for clear Tamil emergency text
        assert result["incident_type"] is not None, (
            f"Groq failed to detect incident_type for Tamil input: {case['text']}"
        )
