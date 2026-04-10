# Design Document — Geo Service (Role 3)

## Overview

The Geo Service is a FastAPI application running on port 8002. It owns all geospatial logic for EIFS: forward geocoding (location string → lat/lon), reverse geocoding (lat/lon → area name), proximity-based candidate lookup for the dedup pipeline, map cluster data for the frontend, and the ERSS mock script + sample dataset.

The service uses a local SQLite database (`hackathon_geo.db`) for caching geocode results and storing incident records during development. In production it would share the PostgreSQL instance with the Backend.

---

## Architecture

```
POST /geocode          → geocoding.py::geocode_location()   → Nominatim (cached)
POST /nearby-incidents → deduplication.py::get_nearby_incidents_logic()
POST /link-incident    → deduplication.py::perform_link_incident() → /nearby-incidents + AI /dedup
GET  /clusters         → main.py (inline)                   → reverse_geocode() for area names
POST /reverse-geocode  → geocoding.py::reverse_geocode()    → Nominatim (cached)

erss_mock.py           → reads scenario JSON → POST http://localhost:8000/reports
data/sample_incidents.json  → static pre-geocoded dataset for frontend dev
```

---

## Components and Interfaces

### `main.py` — FastAPI Application

Exposes all HTTP endpoints. Delegates business logic to `geocoding.py` and `deduplication.py`.

Known bug to fix: `api_geocode` passes `req.city` / `req.state` instead of `req.city_hint` / `req.state_hint`.

### `geocoding.py` — Geocoding Logic

- `normalize_text(text)` — lowercase + strip punctuation, used as cache key
- `geocode_location(location_text, city_hint, state_hint)` — forward geocode with Nominatim, ArcGIS fallback, SQLite cache
- `reverse_geocode(lat, lon)` — reverse geocode with Nominatim, SQLite cache at 3 decimal precision
- `extract_landmarks(lat, lon)` — bonus: pulls nearby amenity names from Nominatim zoom=17

### `deduplication.py` — Proximity & Linking Logic

- `haversine(lat1, lon1, lat2, lon2)` — pure math, returns distance in metres
- `get_nearby_incidents_logic(lat, lon, radius_m, within_minutes)` — queries Incident table, filters by Haversine + time window, returns sorted list
- `perform_link_incident(lat, lon, summary, reported_time)` — Stage 1 geo filter + Stage 2 AI /dedup call, combined scoring, returns best match

### `models.py` — SQLAlchemy Models

Tables: `Incident`, `GeocodeCache`, `ReverseGeocodeCache`.

Known bug to fix: `GeocodeCache` is missing the `landmarks` column.

### `erss_mock.py` — ERSS Simulator

Standalone script. Reads a JSON scenario file, POSTs each report to Backend with configurable delay. Supports `--speed` flag.

Missing: the scenario JSON file (`data/demo_scenario.json`).

### `sample_dataset.py` → `data/sample_incidents.py`

Currently a duplicate of `geocoding.py`. Needs to be replaced with a script that generates `data/sample_incidents.json` — 20+ pre-geocoded incidents across 5+ Chennai/Bengaluru areas.

---

## Data Models

### `GeocodeCache` (fix needed)

```python
class GeocodeCache(Base):
    __tablename__ = 'geocode_cache'
    id           = Column(String, primary_key=True, default=generate_uuid)
    query        = Column(String, unique=True, index=True)
    lat          = Column(Float, nullable=True)
    lon          = Column(Float, nullable=True)
    resolved_name = Column(String, nullable=True)
    landmarks    = Column(String, nullable=True)  # ← missing, needs to be added
```

### `Incident` (existing, correct)

```python
class Incident(Base):
    __tablename__ = 'incidents'
    id            = Column(String, primary_key=True)
    summary       = Column(Text)
    lat           = Column(Float)
    lon           = Column(Float)
    created_at    = Column(DateTime)
    updated_at    = Column(DateTime)
    severity_label = Column(String)
    report_count  = Column(Integer)
    area_name     = Column(String, nullable=True)
```

### `ReverseGeocodeCache` (existing, correct)

```python
class ReverseGeocodeCache(Base):
    __tablename__ = 'reverse_geocode_cache'
    id          = Column(String, primary_key=True)
    lat_rounded = Column(Float, index=True)
    lon_rounded = Column(Float, index=True)
    area_name   = Column(String, nullable=True)
    district    = Column(String, nullable=True)
    city        = Column(String, nullable=True)
```

### `data/sample_incidents.json` schema

```json
[
  {
    "incident_id": "uuid-string",
    "incident_type": "road_accident | fire | medical | flood | crime",
    "lat": 13.0827,
    "lon": 80.2707,
    "severity_label": "Critical | High | Medium | Low",
    "area_name": "Anna Nagar",
    "report_count": 3
  }
]
```

### `data/demo_scenario.json` schema

```json
[
  {
    "modality": "voice | text | image",
    "raw_text": "...",
    "source": "98XXXXXXXX"
  }
]
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

PBT applies here because the Geo Service has several pure-logic components (Haversine distance, combined scoring formula, cache lookup, cluster grouping) with large input spaces where 100+ iterations meaningfully increase confidence. Nominatim network calls are excluded from PBT and covered by integration tests.

**Library:** `hypothesis` (Python)

**Tag format:** `# Feature: geo-service, Property N: <property_text>`

---

### Property 1: Geocode response schema completeness

*For any* non-empty location string submitted to `geocode_location`, the returned tuple SHALL always contain exactly four elements: `lat` (float or None), `lon` (float or None), `confidence` (float in [0.0, 1.0]), and `resolved_name` (string or None) — never missing, never wrong type.

**Validates: Requirements R3-1.1**

---

### Property 2: Geocoding cache idempotence

*For any* location string that has already been geocoded and cached, calling `geocode_location` again with the same normalized input SHALL return identical `lat`, `lon`, `confidence`, and `resolved_name` values. Similarly, for any lat/lon pair that has been reverse-geocoded and cached, calling `reverse_geocode` again SHALL return identical `area_name`, `district`, and `city` values.

**Validates: Requirements R3-1.5, R3-5.3**

---

### Property 3: Haversine symmetry and non-negativity

*For any* two coordinate pairs (lat1, lon1) and (lat2, lon2) with valid values, the Haversine distance SHALL be non-negative, and `haversine(lat1, lon1, lat2, lon2)` SHALL equal `haversine(lat2, lon2, lat1, lon1)`. Additionally, `haversine(lat, lon, lat, lon)` SHALL equal 0.0.

**Validates: Requirements R3-2.2**

---

### Property 4: Nearby incidents sorted ascending

*For any* coordinate and time window, the list returned by `get_nearby_incidents_logic` SHALL be sorted by `distance_m` in ascending order — the closest incident is always first.

**Validates: Requirements R3-2.3**

---

### Property 5: Nearby incidents within radius

*For any* coordinate, radius, and time window, every incident in the returned list SHALL have `distance_m` ≤ `radius_m`. No incident outside the radius SHALL appear in the results.

**Validates: Requirements R3-2.1, R3-2.2**

---

### Property 6: Combined score formula correctness

*For any* `geo_score` in [0.0, 1.0] and `semantic_score` in [0.0, 1.0], the combined score computed by `perform_link_incident` SHALL equal exactly `0.4 * geo_score + 0.6 * semantic_score`. When the combined score is below 0.65, the returned `incident_id` SHALL be `None`.

**Validates: Requirements R3-3.3, R3-3.5**

---

### Property 7: Cluster count at high zoom equals incident count

*For any* set of N incidents with valid coordinates, calling `GET /clusters` with `zoom >= 12` SHALL return exactly N items — one per incident, no grouping applied.

**Validates: Requirements R3-4.4**

---

### Property 8: Cluster count at low zoom ≤ incident count

*For any* set of N incidents with valid coordinates, calling `GET /clusters` with `zoom < 12` SHALL return a list of length ≤ N. Incidents within 1 km of each other SHALL be grouped into the same cluster.

**Validates: Requirements R3-4.3**

---

### Property 9: Sample dataset schema validity

*For every* record in `data/sample_incidents.json`, the record SHALL contain all seven required fields (`incident_id`, `incident_type`, `lat`, `lon`, `severity_label`, `area_name`, `report_count`) with correct types, and the dataset SHALL contain at least 20 records spanning at least 5 distinct `area_name` values.

**Validates: Requirements R3-7.1, R3-7.2**

---

## Error Handling

| Condition | Behaviour |
|---|---|
| Empty `location_text` | Return `{lat: null, lon: null, confidence: 0.0, resolved_name: null}` immediately |
| Nominatim timeout | Catch `GeocoderTimedOut`, return null result, log warning |
| Nominatim no result | Fall back to ArcGIS; if ArcGIS also fails, cache null result and return null |
| AI Service `/dedup` unreachable | Fall back to keyword-overlap mock similarity in `_mock_role2_dedup_call` |
| Invalid bbox format in `/clusters` | Return HTTP 400 with descriptive error |
| `incidents` table empty | `/nearby-incidents` and `/clusters` return empty list with HTTP 200 |

---

## Testing Strategy

### Dual Testing Approach

Unit tests cover specific examples, edge cases, and error conditions. Property-based tests verify universal invariants across randomly generated inputs. Both are required.

### Property-Based Testing

**Library:** `hypothesis`

**Configuration:** minimum 100 iterations per property test (`@settings(max_examples=100)`).

**Tag format:**
```python
# Feature: geo-service, Property N: <property_text>
```

Each of the 9 correctness properties above maps to exactly one `@given`-decorated test function.

### Unit Tests

- `normalize_text`: empty string, string with punctuation, already-normalized string
- `geocode_location`: cache hit path (no Nominatim call), null result path
- `haversine`: known distance (Chennai Central ↔ Anna Nagar ≈ 7 km), same-point = 0
- `get_nearby_incidents_logic`: empty DB returns `[]`, incident exactly at radius boundary
- `perform_link_incident`: no candidates → returns `(None, 0.0, "No matching incident found")`
- `POST /geocode` endpoint: missing `location_text` → HTTP 422
- `POST /nearby-incidents` endpoint: valid request → HTTP 200 with list
- Sample dataset: file exists, loads as valid JSON

### Integration Tests (manual / demo)

- Submit report via `erss_mock.py` → verify Backend receives it
- Full pipeline: geocode → nearby → link → verify incident linked correctly
