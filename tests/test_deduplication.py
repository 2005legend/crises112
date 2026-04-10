"""
tests/test_deduplication.py — unit and property tests for deduplication.py
"""
import datetime
import uuid
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from hypothesis import given, settings
import hypothesis.strategies as st

from models import Base, Incident
from deduplication import haversine, get_nearby_incidents_logic, perform_link_incident


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _add_incident(session, lat, lon, summary="test", minutes_ago=5):
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
# Unit tests — haversine  (R3-2.2)
# ---------------------------------------------------------------------------

def test_haversine_same_point_is_zero():
    assert haversine(13.0827, 80.2707, 13.0827, 80.2707) == 0.0


def test_haversine_known_distance_chennai():
    """Chennai Central ↔ Anna Nagar should be roughly 5–7 km."""
    dist = haversine(13.0827, 80.2707, 13.0878, 80.2185)
    assert 4000 < dist < 8000, f"Expected ~5-7 km, got {dist:.0f} m"


def test_haversine_is_symmetric():
    d1 = haversine(13.0827, 80.2707, 13.0418, 80.2341)
    d2 = haversine(13.0418, 80.2341, 13.0827, 80.2707)
    assert abs(d1 - d2) < 0.001


# ---------------------------------------------------------------------------
# Property 3: Haversine symmetry and non-negativity  (R3-2.2)
# ---------------------------------------------------------------------------

lat_st = st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False)
lon_st = st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False)

# Feature: geo-service, Property 3: Haversine symmetry and non-negativity
@settings(max_examples=100)
@given(lat_st, lon_st, lat_st, lon_st)
def test_property_haversine_symmetry_and_non_negativity(lat1, lon1, lat2, lon2):
    """
    Property 3: Haversine symmetry and non-negativity
    Validates: Requirements R3-2.2
    """
    d_ab = haversine(lat1, lon1, lat2, lon2)
    d_ba = haversine(lat2, lon2, lat1, lon1)
    d_aa = haversine(lat1, lon1, lat1, lon1)

    assert d_ab >= 0
    assert abs(d_ab - d_ba) < 1e-6
    assert d_aa == 0.0


# ---------------------------------------------------------------------------
# Property 4: Nearby incidents sorted ascending  (R3-2.3)
# ---------------------------------------------------------------------------

# Feature: geo-service, Property 4: Nearby incidents sorted ascending
@settings(max_examples=100)
@given(
    st.lists(
        st.tuples(
            st.floats(min_value=12.5, max_value=13.5, allow_nan=False, allow_infinity=False),
            st.floats(min_value=79.5, max_value=81.0, allow_nan=False, allow_infinity=False),
        ),
        min_size=0,
        max_size=20,
    )
)
def test_property_nearby_incidents_sorted_ascending(coords):
    """
    Property 4: Nearby incidents sorted ascending
    Validates: Requirements R3-2.3
    """
    session = _make_session()
    for lat, lon in coords:
        _add_incident(session, lat, lon, minutes_ago=5)

    with patch("deduplication.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__ = lambda s: session
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        results = get_nearby_incidents_logic(13.0827, 80.2707, radius_m=500000, within_minutes=60)

    distances = [r["distance_m"] for r in results]
    assert distances == sorted(distances)
    session.close()


# ---------------------------------------------------------------------------
# Property 5: Nearby incidents within radius  (R3-2.1, R3-2.2)
# ---------------------------------------------------------------------------

# Feature: geo-service, Property 5: Nearby incidents within radius
@settings(max_examples=100)
@given(
    st.lists(
        st.tuples(
            st.floats(min_value=12.5, max_value=13.5, allow_nan=False, allow_infinity=False),
            st.floats(min_value=79.5, max_value=81.0, allow_nan=False, allow_infinity=False),
        ),
        min_size=0,
        max_size=20,
    ),
    st.integers(min_value=100, max_value=50000),
)
def test_property_nearby_incidents_within_radius(coords, radius_m):
    """
    Property 5: Nearby incidents within radius
    Validates: Requirements R3-2.1, R3-2.2
    """
    session = _make_session()
    for lat, lon in coords:
        _add_incident(session, lat, lon, minutes_ago=5)

    with patch("deduplication.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__ = lambda s: session
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        results = get_nearby_incidents_logic(13.0827, 80.2707, radius_m=radius_m, within_minutes=60)

    for r in results:
        assert r["distance_m"] <= radius_m, (
            f"Incident at distance {r['distance_m']:.1f} m exceeds radius {radius_m} m"
        )
    session.close()
