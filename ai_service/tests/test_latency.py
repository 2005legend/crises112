"""
Latency validation tests.
Marked @pytest.mark.slow — skip in fast CI with: pytest -m "not slow"
"""
import json
import time
import pytest
from unittest.mock import patch


VALID_EXTRACTION = {
    "incident_type": "road_accident",
    "location_string": "Anna Nagar",
    "time_reference": None,
    "victim_count": 2,
    "risk_keywords": ["accident", "injured"],
    "summary": "Road accident near Anna Nagar with 2 injured.",
}


@pytest.mark.slow
def test_extract_fields_completes_within_2s():
    """
    extract_fields with a short text must complete in <= 2s when Groq is mocked.
    Validates: R2-3.5
    """
    with patch("engines.extraction._call_groq", return_value=json.dumps(VALID_EXTRACTION)):
        from engines.extraction import extract_fields
        start = time.perf_counter()
        result = extract_fields("Fire near Anna Nagar signal, 2 people injured.")
        elapsed = time.perf_counter() - start

    assert elapsed <= 2.0, f"extract_fields took {elapsed:.3f}s, expected <= 2s"
    assert "incident_type" in result


@pytest.mark.slow
def test_find_match_50_candidates_within_500ms():
    """
    find_match with 50 candidates must complete in <= 500ms using real MiniLM.
    Validates: R2-4.6
    """
    from engines.dedup import find_match

    candidates = [
        {"incident_id": f"INC-{i}", "summary": f"Emergency incident number {i} at location {i}"}
        for i in range(50)
    ]
    summary = "Road accident near Anna Nagar signal with 2 injured persons."

    start = time.perf_counter()
    result = find_match(summary, candidates)
    elapsed = time.perf_counter() - start

    assert elapsed <= 0.5, f"find_match with 50 candidates took {elapsed:.3f}s, expected <= 500ms"


@pytest.mark.slow
def test_fuse_text_pipeline_within_3s():
    """
    Full fuse pipeline for text modality must complete in <= 3s when Groq is mocked.
    Validates: R2-5.4
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from fastapi.testclient import TestClient

    with patch("engines.extraction._call_groq", return_value=json.dumps(VALID_EXTRACTION)):
        from main import app
        client = TestClient(app)

        start = time.perf_counter()
        response = client.post(
            "/ai/fuse-report",
            data={
                "modality": "text",
                "text": "Fire near Anna Nagar signal, 2 people injured.",
            },
        )
        elapsed = time.perf_counter() - start

    assert elapsed <= 3.0, f"Fuse text pipeline took {elapsed:.3f}s, expected <= 3s"
    assert response.status_code == 200
