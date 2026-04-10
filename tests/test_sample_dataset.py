"""
tests/test_sample_dataset.py — property test for sample dataset schema validity
Feature: geo-service, Property 9: Sample dataset schema validity
Validates: Requirements R3-7.1, R3-7.2
"""
import json
import os
import pytest

DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sample_incidents.json")
REQUIRED_FIELDS = {"incident_id", "incident_type", "lat", "lon", "severity_label", "area_name", "report_count"}


@pytest.fixture(scope="module")
def sample_data():
    with open(DATASET_PATH, "r") as f:
        return json.load(f)


# Feature: geo-service, Property 9: Sample dataset schema validity
def test_property_sample_dataset_schema_validity(sample_data):
    """
    Property 9: Sample dataset schema validity
    Validates: Requirements R3-7.1, R3-7.2
    For every record in data/sample_incidents.json:
    - All 7 required fields present with correct types
    - At least 20 records
    - At least 5 distinct area_name values
    """
    # R3-7.1: at least 20 records
    assert len(sample_data) >= 20, f"Expected >= 20 records, got {len(sample_data)}"

    for i, record in enumerate(sample_data):
        # All required fields present
        missing = REQUIRED_FIELDS - set(record.keys())
        assert not missing, f"Record {i} missing fields: {missing}"

        # Type checks
        assert isinstance(record["incident_id"], str), f"Record {i}: incident_id must be str"
        assert isinstance(record["incident_type"], str), f"Record {i}: incident_type must be str"
        assert isinstance(record["lat"], (int, float)), f"Record {i}: lat must be numeric"
        assert isinstance(record["lon"], (int, float)), f"Record {i}: lon must be numeric"
        assert isinstance(record["severity_label"], str), f"Record {i}: severity_label must be str"
        assert isinstance(record["area_name"], str), f"Record {i}: area_name must be str"
        assert isinstance(record["report_count"], int), f"Record {i}: report_count must be int"

        # Coordinate sanity
        assert -90 <= record["lat"] <= 90, f"Record {i}: lat out of range"
        assert -180 <= record["lon"] <= 180, f"Record {i}: lon out of range"

    # R3-7.2: at least 5 distinct areas
    areas = {r["area_name"] for r in sample_data}
    assert len(areas) >= 5, f"Expected >= 5 distinct area_name values, got {len(areas)}: {areas}"
