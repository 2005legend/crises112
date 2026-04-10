"""
tests/test_geocoding.py — unit and property tests for geocoding.py
"""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, GeocodeCache
from geocoding import normalize_text, geocode_location, reverse_geocode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


# ---------------------------------------------------------------------------
# Unit tests — normalize_text  (R3-1.5)
# ---------------------------------------------------------------------------

def test_normalize_empty_string():
    assert normalize_text("") == ""

def test_normalize_none_like_falsy():
    # normalize_text guards against falsy values
    assert normalize_text(None) == ""  # type: ignore[arg-type]

def test_normalize_strips_punctuation():
    assert normalize_text("Anna Nagar!") == "anna nagar"

def test_normalize_lowercases():
    assert normalize_text("CHENNAI CENTRAL") == "chennai central"

def test_normalize_mixed():
    assert normalize_text("T. Nagar, Chennai!") == "t nagar chennai"


# ---------------------------------------------------------------------------
# Unit tests — geocode_location cache path  (R3-1.5)
# ---------------------------------------------------------------------------

def test_geocode_cache_hit_returns_same_result():
    """Second call with same input must return cached values without hitting Nominatim."""
    session = _make_session()

    # Pre-populate cache
    cached = GeocodeCache(
        query="anna nagar",
        lat=13.0878,
        lon=80.2185,
        resolved_name="Anna Nagar, Chennai",
        landmarks="Park",
    )
    session.add(cached)
    session.commit()

    with patch("geocoding.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__ = lambda s: session
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("geocoding.geolocator") as mock_geo:
            lat, lon, conf, resolved, landmarks = geocode_location("Anna Nagar!")
            # Nominatim must NOT have been called
            mock_geo.geocode.assert_not_called()

    assert lat == 13.0878
    assert lon == 80.2185
    assert conf == 1.0
    assert resolved == "Anna Nagar, Chennai"
    session.close()


def test_geocode_null_result_when_both_providers_fail():
    """When Nominatim and ArcGIS both fail, returns (None, None, 0.0, None, None)."""
    session = _make_session()

    with patch("geocoding.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__ = lambda s: session
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("geocoding._rate_limit"):
            with patch("geocoding.geolocator") as mock_nom:
                mock_nom.geocode.return_value = None
                with patch("geocoding.ArcGIS") as mock_arcgis_cls:
                    mock_arcgis_cls.return_value.geocode.return_value = None
                    result = geocode_location("xyzzy nonexistent place 99999")

    assert result == (None, None, 0.0, None, None)
    session.close()


# ---------------------------------------------------------------------------
# Unit tests — property 6.2 & 6.3 (schema + idempotence) via unit path
# ---------------------------------------------------------------------------

def test_geocode_returns_five_tuple_on_cache_miss_null():
    """Return value always has exactly 5 elements even on null path."""
    session = _make_session()

    with patch("geocoding.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__ = lambda s: session
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("geocoding._rate_limit"):
            with patch("geocoding.geolocator") as mock_nom:
                mock_nom.geocode.return_value = None
                with patch("geocoding.ArcGIS") as mock_arcgis_cls:
                    mock_arcgis_cls.return_value.geocode.return_value = None
                    result = geocode_location("nowhere land")

    assert len(result) == 5
    lat, lon, conf, resolved, landmarks = result
    assert lat is None
    assert lon is None
    assert isinstance(conf, float)
    assert 0.0 <= conf <= 1.0
    session.close()


# ---------------------------------------------------------------------------
# Property test 6.2 — Geocode response schema completeness  (R3-1.1)
# ---------------------------------------------------------------------------
from hypothesis import given, settings
import hypothesis.strategies as st

# Feature: geo-service, Property 1: Geocode response schema completeness
@settings(max_examples=100)
@given(st.text(min_size=1, alphabet=st.characters(blacklist_categories=("Cs",))))
def test_property_geocode_schema_completeness(location_text):
    """
    Property 1: Geocode response schema completeness
    Validates: Requirements R3-1.1
    For any non-empty location string, geocode_location always returns a 5-tuple
    with correct types.
    """
    session = _make_session()

    with patch("geocoding.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__ = lambda s: session
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("geocoding._rate_limit"):
            with patch("geocoding.geolocator") as mock_nom:
                mock_nom.geocode.return_value = None
                with patch("geocoding.ArcGIS") as mock_arcgis_cls:
                    mock_arcgis_cls.return_value.geocode.return_value = None
                    result = geocode_location(location_text)

    assert len(result) == 5
    lat, lon, conf, resolved, landmarks = result
    assert lat is None or isinstance(lat, float)
    assert lon is None or isinstance(lon, float)
    assert isinstance(conf, float)
    assert 0.0 <= conf <= 1.0
    assert resolved is None or isinstance(resolved, str)
    assert landmarks is None or isinstance(landmarks, str)
    session.close()


# ---------------------------------------------------------------------------
# Property test 6.3 — Geocoding cache idempotence  (R3-1.5, R3-5.3)
# ---------------------------------------------------------------------------

# Feature: geo-service, Property 2: Geocoding cache idempotence
@settings(max_examples=100)
@given(st.text(min_size=1, alphabet=st.characters(blacklist_categories=("Cs",))))
def test_property_geocode_cache_idempotence(location_text):
    """
    Property 2: Geocoding cache idempotence
    Validates: Requirements R3-1.5, R3-5.3
    Calling geocode_location twice with the same input returns identical results.
    """
    session = _make_session()

    mock_location = MagicMock()
    mock_location.latitude = 13.0827
    mock_location.longitude = 80.2707
    mock_location.address = "Chennai Central"

    with patch("geocoding.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__ = lambda s: session
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("geocoding._rate_limit"):
            with patch("geocoding.extract_landmarks", return_value="Station"):
                with patch("geocoding.geolocator") as mock_nom:
                    mock_nom.geocode.return_value = mock_location
                    result1 = geocode_location(location_text)
                    result2 = geocode_location(location_text)

    # lat, lon, resolved_name, landmarks must be identical on repeated calls.
    # confidence may differ (0.9 on first call, 1.0 on cache hit) — that is expected.
    assert result1[0] == result2[0]  # lat
    assert result1[1] == result2[1]  # lon
    assert result1[3] == result2[3]  # resolved_name
    assert result1[4] == result2[4]  # landmarks
    session.close()
