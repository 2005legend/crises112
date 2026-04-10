# Requirements – Role 3: Geospatial & Integrations

## Introduction

Role 3 owns the geocoding and spatial deduplication layer of EIFS. It converts raw location strings into lat/lon coordinates using Nominatim, provides proximity-based candidate incident lookup for the dedup pipeline, and supplies map-ready cluster data to the frontend. It also owns the mock ERSS integration script that simulates incoming reports during the demo.

---

## Glossary

- **Geo_Service**: The FastAPI service (or internal Python module) that geocodes location strings and performs spatial queries.
- **Nominatim**: The OpenStreetMap geocoding API used to resolve place names to coordinates.
- **Haversine**: The formula used to compute great-circle distance between two lat/lon points.
- **Proximity_Window**: The spatial and temporal bounds used to find candidate incidents for dedup — 500 m radius, 30-minute time window.
- **Cluster**: A group of incidents within close proximity displayed as a single map marker at low zoom levels.
- **ERSS_Mock**: A script that emits synthetic report events as if from India's 112 command room, hitting the Backend ingest endpoint.

---

## Requirements

### Requirement R3-1: Geocoding Endpoint

**User Story:** As a backend developer, I want to send a raw location string and receive lat/lon coordinates, so that reports can be placed on a map and spatially matched to nearby incidents.

#### Acceptance Criteria

1. THE Geo_Service SHALL expose `POST /geocode` accepting `{"location_text": "<string>", "city_hint": "<string, optional>", "state_hint": "<string, optional>"}` and returning `{"lat": <float or null>, "lon": <float or null>, "confidence": <float 0–1>, "resolved_name": "<string or null>"}`.
2. THE Geo_Service SHALL query Nominatim with the provided location text and optional city/state context to improve resolution accuracy.
3. IF Nominatim returns no result, THE Geo_Service SHALL return `{"lat": null, "lon": null, "confidence": 0.0, "resolved_name": null}` and log the unresolved string.
4. THE Geo_Service SHALL complete geocoding within 3 seconds per request.
5. THE Geo_Service SHALL cache geocoding results keyed by normalized location text (lowercased, stripped of punctuation) to avoid redundant Nominatim calls for identical strings.
6. THE Geo_Service SHALL respect Nominatim's usage policy by enforcing a minimum 1-second delay between outbound requests to the public Nominatim instance.

---

### Requirement R3-2: Proximity-Based Candidate Lookup

**User Story:** As a backend developer, I want to query for open incidents near a given coordinate within a time window, so that the dedup engine has a shortlist of candidates to compare against.

#### Acceptance Criteria

1. THE Geo_Service SHALL expose `POST /nearby-incidents` accepting `{"lat": <float>, "lon": <float>, "radius_m": <int, default 500>, "within_minutes": <int, default 30>}` and returning a list of `{"incident_id": "<id>", "distance_m": <float>, "summary": "<string>"}` objects.
2. THE Geo_Service SHALL compute distances using the Haversine formula or PostGIS `ST_DWithin` if PostGIS is available.
3. THE response list SHALL be sorted by distance ascending (closest first).
4. IF no incidents are found within the window, THE endpoint SHALL return an empty list with HTTP 200.
5. THE Geo_Service SHALL complete the proximity query within 500 milliseconds.

---

### Requirement R3-3: Combined Geo + Semantic Incident Linking

**User Story:** As a backend developer, I want a single call that returns the best incident to link a new report to, combining geo proximity and semantic similarity scores, so that Role 1 only needs one integration point for incident assignment.

#### Acceptance Criteria

1. THE Geo_Service SHALL expose `POST /link-incident` accepting `{"lat": <float or null>, "lon": <float or null>, "summary": "<string>", "reported_time": "<ISO timestamp>"}` and returning `{"incident_id": "<id> or null", "confidence": <float>, "reason": "<string>"}`.
2. WHEN `lat` and `lon` are provided, THE endpoint SHALL first fetch nearby candidates using the proximity window, then pass them to Role 2's `/dedup` endpoint to get semantic similarity scores.
3. THE endpoint SHALL select the candidate with the highest combined score (geo proximity weight 0.4 + semantic similarity weight 0.6) as the match.
4. WHEN `lat` and `lon` are null, THE endpoint SHALL skip geo filtering and pass all open incidents from the last 30 minutes as candidates to the dedup endpoint.
5. WHEN no candidate scores above the combined threshold of 0.65, THE endpoint SHALL return `{"incident_id": null, "confidence": <best score>, "reason": "No matching incident found"}`.

---

### Requirement R3-4: Map Cluster Data

**User Story:** As a frontend developer, I want an endpoint that returns incident locations grouped into clusters, so that the Leaflet map can display clean cluster markers at low zoom levels.

#### Acceptance Criteria

1. THE Geo_Service SHALL expose `GET /clusters` accepting optional query parameters `zoom` (integer 1–18, default 10) and `bbox` (bounding box as `min_lat,min_lon,max_lat,max_lon`).
2. THE response SHALL return a list of cluster objects: `{"cluster_id": "<string>", "lat": <float>, "lon": <float>, "incident_count": <int>, "max_severity_label": "<string>", "area_name": "<string or null>"}`.
3. AT zoom levels below 12, THE Geo_Service SHALL group incidents within 1 km of each other into a single cluster.
4. AT zoom levels 12 and above, THE Geo_Service SHALL return individual incident markers rather than clusters.
5. THE `area_name` field SHALL be populated by reverse-geocoding the cluster centroid to a neighbourhood or district name using Nominatim.

---

### Requirement R3-5: Area Labelling

**User Story:** As a frontend developer, I want incident coordinates reverse-geocoded to human-readable area names, so that the dashboard can display "Anna Nagar" instead of raw coordinates.

#### Acceptance Criteria

1. THE Geo_Service SHALL expose `POST /reverse-geocode` accepting `{"lat": <float>, "lon": <float>}` and returning `{"area_name": "<string or null>", "district": "<string or null>", "city": "<string or null>"}`.
2. THE Geo_Service SHALL use Nominatim reverse geocoding to resolve coordinates to the most specific available administrative boundary name.
3. THE Geo_Service SHALL cache reverse geocoding results keyed by coordinates rounded to 3 decimal places (approximately 100 m precision).

---

### Requirement R3-6: ERSS Mock Integration

**User Story:** As a demo presenter, I want a script that simulates a stream of emergency reports arriving from the 112 command room, so that the live demo shows the full pipeline working end-to-end without real callers.

#### Acceptance Criteria

1. THE ERSS_Mock SHALL be a standalone Python script that reads a JSON scenario file and POSTs each report to the Backend's `POST /reports` endpoint with a configurable delay between submissions (default 2 seconds).
2. THE scenario file SHALL include at least one demo scenario with 8–10 reports describing the same road accident from different modalities (voice transcript, SMS text, image caption) and different callers.
3. THE ERSS_Mock SHALL print a log line for each submitted report showing: report number, modality, truncated text, and HTTP response status.
4. THE ERSS_Mock SHALL support a `--speed` flag that multiplies the delay (e.g., `--speed 0.5` halves the delay for a faster demo).

---

### Requirement R3-7: Geocoded Sample Dataset

**User Story:** As a frontend developer, I want a pre-geocoded sample dataset of incidents, so that I can build and test the Leaflet map without waiting for the live pipeline.

#### Acceptance Criteria

1. THE Geo_Service team SHALL provide a JSON or CSV file containing at least 20 geocoded sample incidents with fields: `incident_id`, `incident_type`, `lat`, `lon`, `severity_label`, `area_name`, `report_count`.
2. THE sample dataset SHALL include incidents spread across at least 5 distinct areas of one Indian city (e.g., Chennai or Bengaluru).
3. THE sample dataset SHALL be committed to the repository at `data/sample_incidents.json` by Hour 6.
