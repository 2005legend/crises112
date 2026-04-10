"""
tests/test_clusters.py — unit and property tests for clustering logic (R3-4)
Tests call _cluster_incidents() directly to avoid httpx/TestClient version issues.
"""
import datetime
import uuid
import pytest
from hypothesis import given, settings
import hypothesis.strategies as st

from models import Incident
from main import _cluster_incidents


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_incident(lat, lon, severity="Low", area=None, report_count=1):
    inc = Incident()
    inc.id = str(uuid.uuid4())
    inc.summary = "test incident"
    inc.lat = lat
    inc.lon = lon
    inc.created_at = datetime.datetime.utcnow()
    inc.updated_at = datetime.datetime.utcnow()
    inc.severity_label = severity
    inc.report_count = report_count
    inc.area_name = area
    return inc


def _no_reverse_geocode(lat, lon):
    return (None, None, None)


# ---------------------------------------------------------------------------
# Unit tests — clustering  (R3-4.3, R3-4.4)
# ---------------------------------------------------------------------------

def test_clusters_high_zoom_returns_one_per_incident():
    """zoom >= 12 → exactly N items, one per incident."""
    incidents = [
        _make_incident(13.0878, 80.2185, area="Anna Nagar"),
        _make_incident(13.0418, 80.2341, area="T. Nagar"),
        _make_incident(13.0012, 80.2565, area="Adyar"),
    ]
    result = _cluster_incidents(incidents, zoom=12, reverse_geocode_fn=_no_reverse_geocode)
    assert len(result) == 3


def test_clusters_low_zoom_groups_nearby_incidents():
    """zoom < 12 with all incidents within 1 km → 1 cluster."""
    # All within ~200m of each other in Anna Nagar
    incidents = [
        _make_incident(13.0878, 80.2185, area="Anna Nagar"),
        _make_incident(13.0880, 80.2187, area="Anna Nagar"),
        _make_incident(13.0876, 80.2183, area="Anna Nagar"),
    ]
    result = _cluster_incidents(incidents, zoom=10, reverse_geocode_fn=_no_reverse_geocode)
    assert len(result) == 1
    assert result[0]["incident_count"] == 3


def test_clusters_empty_db_returns_empty_list():
    result = _cluster_incidents([], zoom=10, reverse_geocode_fn=_no_reverse_geocode)
    assert result == []


def test_clusters_high_zoom_preserves_incident_fields():
    inc = _make_incident(13.0878, 80.2185, severity="Critical", area="Anna Nagar", report_count=5)
    result = _cluster_incidents([inc], zoom=15, reverse_geocode_fn=_no_reverse_geocode)
    assert len(result) == 1
    assert result[0]["lat"] == 13.0878
    assert result[0]["lon"] == 80.2185
    assert result[0]["max_severity_label"] == "Critical"
    assert result[0]["incident_count"] == 5
    assert result[0]["area_name"] == "Anna Nagar"


# ---------------------------------------------------------------------------
# Property 7: Cluster count at high zoom equals incident count  (R3-4.4)
# ---------------------------------------------------------------------------

lat_st = st.floats(min_value=12.5, max_value=13.5, allow_nan=False, allow_infinity=False)
lon_st = st.floats(min_value=79.5, max_value=81.0, allow_nan=False, allow_infinity=False)

# Feature: geo-service, Property 7: Cluster count at high zoom equals incident count
@settings(max_examples=100)
@given(
    st.lists(
        st.tuples(lat_st, lon_st),
        min_size=0,
        max_size=15,
    )
)
def test_property_cluster_high_zoom_equals_incident_count(coords):
    """
    Property 7: Cluster count at high zoom equals incident count
    Validates: Requirements R3-4.4
    """
    incidents = [_make_incident(lat, lon) for lat, lon in coords]
    result = _cluster_incidents(incidents, zoom=12, reverse_geocode_fn=_no_reverse_geocode)
    assert len(result) == len(coords)


# ---------------------------------------------------------------------------
# Property 8: Cluster count at low zoom ≤ incident count  (R3-4.3)
# ---------------------------------------------------------------------------

# Feature: geo-service, Property 8: Cluster count at low zoom <= incident count
@settings(max_examples=100)
@given(
    st.lists(
        st.tuples(lat_st, lon_st),
        min_size=0,
        max_size=15,
    )
)
def test_property_cluster_low_zoom_lte_incident_count(coords):
    """
    Property 8: Cluster count at low zoom <= incident count
    Validates: Requirements R3-4.3
    """
    incidents = [_make_incident(lat, lon) for lat, lon in coords]
    result = _cluster_incidents(incidents, zoom=10, reverse_geocode_fn=_no_reverse_geocode)
    assert len(result) <= len(coords)
