# Implementation Plan: Geo Service (Role 3)

## Overview

Fix existing bugs, fill in missing files, and add tests. All tasks build incrementally — bugs first, then missing data files, then tests.

## Tasks

- [x] 1. Fix models.py — add missing landmarks column to GeocodeCache
  - Add `landmarks = Column(String, nullable=True)` to `GeocodeCache`
  - Drop and recreate the SQLite table (delete `hackathon_geo.db` and call `init_db()`) to apply schema change
  - _Requirements: R3-1_

- [x] 2. Fix main.py — correct field name bug in api_geocode
  - Change `req.city` → `req.city_hint` and `req.state` → `req.state_hint` in `api_geocode` (currently on lines ~33–34)
  - Verify all other endpoint handlers use correct Pydantic field names
  - _Requirements: R3-1.1_

- [x] 3. Create demo scenario JSON file for ERSS mock
  - Create `data/` directory
  - Create `data/demo_scenario.json` with 8–10 reports about the same road accident
  - Include mix of modalities: `voice`, `text`, `image`
  - Use different `source` values (phone numbers) per report
  - _Requirements: R3-6.2_

- [x] 4. Replace sample_dataset.py with a proper sample incidents generator
  - Rewrite `sample_dataset.py` as a standalone script that outputs `data/sample_incidents.json`
  - Generate 20+ incidents across 5+ distinct Chennai/Bengaluru areas with all required fields: `incident_id`, `incident_type`, `lat`, `lon`, `severity_label`, `area_name`, `report_count`
  - Run the script to produce `data/sample_incidents.json`
  - _Requirements: R3-7.1, R3-7.2_

- [x] 5. Set up testing infrastructure
  - Add `hypothesis` to `requirements.txt`
  - Create `tests/` directory with `__init__.py` and `conftest.py`
  - Add fixtures in `conftest.py`: in-memory SQLite DB session, sample `Incident` rows
  - _Requirements: all_

- [x] 6. Implement unit and property tests for geocoding
  - [x] 6.1 Write unit tests for normalize_text and geocode_location cache path
    - Test empty string → returns `""`
    - Test punctuation stripping (e.g. `"Anna Nagar!"` → `"anna nagar"`)
    - Test cache hit: second call with same input returns same result without hitting Nominatim
    - Test null result path (both Nominatim and ArcGIS fail → returns `(None, None, 0.0, None, None)`)
    - _Requirements: R3-1.3, R3-1.5_

  - [ ] 6.2 Write property test for geocode response schema completeness
    - **Property 1: Geocode response schema completeness**
    - **Validates: Requirements R3-1.1**
    - Use `@given(st.text(min_size=1))` over `geocode_location` with mocked Nominatim
    - Assert all five return values are present with correct types (`lat`/`lon` float or None, `confidence` float in [0,1], `resolved_name` str or None, `landmarks` str or None)

  - [ ] 6.3 Write property test for geocoding cache idempotence
    - **Property 2: Geocoding cache idempotence**
    - **Validates: Requirements R3-1.5, R3-5.3**
    - Call `geocode_location` twice with same input against in-memory DB, assert identical results
    - Call `reverse_geocode` twice with same lat/lon, assert identical results

- [x] 7. Implement unit and property tests for Haversine and proximity lookup
  - [x] 7.1 Write unit tests for haversine
    - Test same-point returns `0.0`
    - Test known distance: Chennai Central (13.0827, 80.2707) ↔ Anna Nagar (13.0878, 80.2185) ≈ 5–6 km
    - _Requirements: R3-2.2_

  - [x] 7.2 Write property test for Haversine symmetry and non-negativity
    - **Property 3: Haversine symmetry and non-negativity**
    - **Validates: Requirements R3-2.2**
    - Use `@given` with lat/lon floats in valid ranges (lat: -90–90, lon: -180–180)
    - Assert `dist >= 0`, `dist(A,B) == dist(B,A)`, `dist(A,A) == 0.0`

  - [ ] 7.3 Write property test for nearby incidents sorted ascending
    - **Property 4: Nearby incidents sorted ascending**
    - **Validates: Requirements R3-2.3**
    - Generate random `Incident` rows in in-memory DB, call `get_nearby_incidents_logic`
    - Assert result list is sorted by `distance_m` ascending

  - [ ] 7.4 Write property test for nearby incidents within radius
    - **Property 5: Nearby incidents within radius**
    - **Validates: Requirements R3-2.1, R3-2.2**
    - Assert every returned incident has `distance_m <= radius_m`

- [x] 8. Implement unit and property tests for link-incident combined scoring
  - [x] 8.1 Write unit tests for perform_link_incident
    - Test no candidates → returns `(None, 0.0, "No matching incident found")`
    - Test best combined score < 0.65 → returns `None` as `incident_id`
    - _Requirements: R3-3.5_

  - [ ] 8.2 Write property test for combined score formula correctness
    - **Property 6: Combined score formula correctness**
    - **Validates: Requirements R3-3.3, R3-3.5**
    - Use `@given` with `geo_score` and `semantic_score` floats in [0, 1]
    - Assert `combined == 0.4 * geo_score + 0.6 * semantic_score`
    - Assert `combined < 0.65` → `incident_id` is `None`

- [x] 9. Implement unit and property tests for cluster endpoint
  - [x] 9.1 Write unit tests for /clusters
    - Test `zoom >= 12` with N incidents returns exactly N items
    - Test `zoom < 12` with all incidents within 1 km of each other returns 1 cluster
    - _Requirements: R3-4.3, R3-4.4_

  - [x] 9.2 Write property test for cluster count at high zoom equals incident count
    - **Property 7: Cluster count at high zoom equals incident count**
    - **Validates: Requirements R3-4.4**
    - Generate N random incidents in in-memory DB, call clustering logic with `zoom=12`, assert `len(result) == N`

  - [x] 9.3 Write property test for cluster count at low zoom ≤ incident count
    - **Property 8: Cluster count at low zoom ≤ incident count**
    - **Validates: Requirements R3-4.3**
    - Generate N random incidents, call clustering logic with `zoom=10`, assert `len(result) <= N`

- [x] 10. Checkpoint — run all tests
  - Run `pytest tests/ -v` and confirm all pass, ask the user if questions arise.

- [x] 11. Write property test for sample dataset schema validity
  - [-] 11.1 Write property test for sample dataset schema validity
    - **Property 9: Sample dataset schema validity**
    - **Validates: Requirements R3-7.1, R3-7.2**
    - Load `data/sample_incidents.json`, assert 20+ records, all seven fields present with correct types
    - Assert at least 5 distinct `area_name` values

- [x] 12. Final checkpoint — ensure all tests pass
  - Run `pytest tests/ -v` and confirm all pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests use `hypothesis` with `@settings(max_examples=100)`
- Unit tests focus on edge cases and error conditions
