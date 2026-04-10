"""
tests/test_link_incident.py — unit and property tests for perform_link_incident
"""
import datetime
import uuid
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from hypothesis import given, settings, assume
import hypothesis.strategies as st

from models import Base, Incident
from deduplication import perform_link_incident


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _add_incident(session, lat, lon, summary="test incident", minutes_ago=5):
    inc = Incident(
        id=str(uuid.uuid4()),
        summary=summary,
        lat=lat,
        lon=lon,
        created_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=minutes_ago),
        updated_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=minutes_ago),
        severity_label="Low",
        report_count=1,
        area_name="Test Area",
    )
    session.add(inc)
    session.commit()
    return inc


# ---------------------------------------------------------------------------
# Unit tests — perform_link_incident  (R3-3.5)
# ---------------------------------------------------------------------------

def test_link_incident_no_candidates_returns_none():
    """No candidates → (None, 0.0, 'No matching incident found')."""
    session = _make_session()  # empty DB

    with patch("deduplication.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__ = lambda s: session
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = perform_link_incident(13.0827, 80.2707, "accident", datetime.datetime.utcnow().isoformat())

    assert result == (None, 0.0, "No matching incident found")
    session.close()


def test_link_incident_low_score_returns_none_id():
    """Best combined score < 0.65 → incident_id is None."""
    session = _make_session()
    # Add incident very far away so geo_score ≈ 0
    _add_incident(session, 12.0, 77.0, summary="completely unrelated event")

    with patch("deduplication.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__ = lambda s: session
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        # Mock dedup call to return low semantic score
        with patch("deduplication.requests.post") as mock_post:
            mock_post.side_effect = Exception("offline")
            incident_id, conf, reason = perform_link_incident(
                13.0827, 80.2707, "xyz abc def", datetime.datetime.utcnow().isoformat()
            )

    assert incident_id is None
    assert conf < 0.65
    session.close()


# ---------------------------------------------------------------------------
# Property 6: Combined score formula correctness  (R3-3.3, R3-3.5)
# ---------------------------------------------------------------------------

score_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Feature: geo-service, Property 6: Combined score formula correctness
@settings(max_examples=100)
@given(score_st, score_st)
def test_property_combined_score_formula(geo_score, semantic_score):
    """
    Property 6: Combined score formula correctness
    Validates: Requirements R3-3.3, R3-3.5
    combined == 0.4 * geo_score + 0.6 * semantic_score
    combined < 0.65 → incident_id is None
    """
    expected_combined = 0.4 * geo_score + 0.6 * semantic_score

    # We test the formula directly by constructing a single candidate
    # whose geo_score and semantic_score we control.
    # geo_score = max(0, 1 - dist/500) → dist = (1 - geo_score) * 500
    dist_m = (1.0 - geo_score) * 500.0

    session = _make_session()
    # Place incident at a known offset from query point
    # We'll use the actual haversine to find a lat/lon that gives dist_m,
    # but it's simpler to mock get_nearby_incidents_logic directly.
    inc_id = str(uuid.uuid4())

    candidates = [{"incident_id": inc_id, "distance_m": dist_m, "summary": "test"}]
    semantic_scores = {inc_id: semantic_score}

    with patch("deduplication.get_nearby_incidents_logic", return_value=candidates):
        with patch("deduplication.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"scores": semantic_scores}
            mock_post.return_value = mock_resp

            result_id, result_conf, result_reason = perform_link_incident(
                13.0827, 80.2707, "test summary", datetime.datetime.utcnow().isoformat()
            )

    assert abs(result_conf - expected_combined) < 1e-9, (
        f"Expected combined {expected_combined:.4f}, got {result_conf:.4f}"
    )

    if expected_combined < 0.65:
        assert result_id is None, f"Expected None for combined={expected_combined:.4f}, got {result_id}"

    session.close()
