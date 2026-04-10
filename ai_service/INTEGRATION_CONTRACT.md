# AI Service ↔ Backend Integration Contract

This document defines exactly how Role 1 (Backend) must consume the AI Service response.
Read this before wiring `POST /ai/fuse-report` into the report ingest flow.

---

## 1. How to call the AI Service

After persisting a raw report to the DB, the Backend fires an async background task:

```python
POST http://localhost:8001/ai/fuse-report
Content-Type: multipart/form-data

modality=<voice|text|image>
text=<raw text>              # for text modality
file=<audio or image>        # for voice/image modality
candidates_json=<JSON array> # see below
```

### candidates_json — CRITICAL

The Backend must populate `candidates_json` with open incidents from the Geo Service's
`POST /nearby-incidents` response. Each candidate must include `distance_m` so the
geo signal in the dedup engine works correctly.

```json
[
  {
    "incident_id": "uuid",
    "summary": "Road accident near Anna Nagar signal",
    "distance_m": 120.0,
    "updated_at": "2024-01-15T14:30:00Z",
    "location_string": "Anna Nagar signal"
  }
]
```

If `distance_m` is missing or null, the geo signal defaults to 0.5 (neutral).
This degrades dedup accuracy — always pass `distance_m` from the Geo Service.

---

## 2. What to store from the response

### From `extracted` (all modalities)

| Field | Store in | Notes |
|---|---|---|
| `extracted.incident_type` | `reports.extracted_json.incident_type` | Used for dedup threshold selection |
| `extracted.location_string` | `reports.location_text` | Pass to Geo Service for geocoding |
| `extracted.risk_keywords` | `reports.extracted_json.risk_keywords` | Fed into Backend severity engine |
| `extracted.summary` | `reports.extracted_json.summary` | Used as dedup text |
| `extracted.victim_count` | `reports.extracted_json.victim_count` | |
| `extracted.field_confidence` | `reports.extracted_json.field_confidence` | |
| `extracted.review_flag` | `reports.review_flag` | Show in dashboard as needs review |
| `extracted.review_reason` | `reports.review_reason` | Show tooltip in dashboard |

### From `match` / `merge_reason`

| Field | Action |
|---|---|
| `match` = `"uuid"` | Link report to that incident via `incident_reports` table |
| `match` = `null` | Create a new incident from this report |
| `merge_reason` | Store in `incident_reports.merge_reason` |
| `similarity_score` | Store in `incident_reports.similarity_score` |
| `combined_score` | Store in `incident_reports.similarity_score` (use combined, not raw semantic) |

### From `vision_analysis` (image modality only)

| Field | Action |
|---|---|
| `vision_analysis.actionable_summary` | Use as initial `incidents.summary` for image reports |
| `vision_analysis.scene_type` | Use as `incidents.incident_type` if extraction returns null |
| `vision_analysis.severity_audit` | Store in `severity_audit` table as report-level metadata |
| `vision_analysis.confidence` | Store in `reports.extracted_json.vision_confidence` |

---

## 3. CRITICAL — Severity scoring resolution

**There are two severity scores in the system. Here is which one wins:**

### Vision severity score (image reports only)
- Computed by the AI Service from the image
- Stored as **report-level metadata** only
- Used as the **initial seed** when creating a new incident from an image report
- Field: `vision_analysis.severity_score`

### Backend severity score (all reports)
- Computed by the Backend's rule-based severity engine
- Runs on the **union of risk_keywords from ALL merged reports**
- **Always overwrites** the incident severity on every merge
- This is the **final, authoritative incident severity**

### Resolution rule (implement this in Role 1):

```python
# When creating a new incident from an image report:
if modality == "image" and vision_analysis:
    incident.severity_score = vision_analysis["severity_score"]  # seed
    incident.severity_label = vision_analysis["severity_label"]  # seed
    # Store vision audit as initial audit rows

# After EVERY report merge (including the first):
all_keywords = union of risk_keywords from all reports linked to this incident
new_score, new_label, new_audit = backend_severity_engine.compute(all_keywords)
incident.severity_score = new_score   # Backend ALWAYS wins
incident.severity_label = new_label
# Replace severity_audit rows with new_audit
```

**Why:** The Backend severity engine uses the full union of keywords from all merged reports,
which is always more complete than a single image analysis. The vision score is a useful
starting point but the Backend score is the ground truth.

---

## 4. review_flag handling

When `review_flag = true` in the response:
- Store it on the report record
- Show a yellow "Needs Review" badge in the dashboard for that report
- Do NOT block incident creation — still process normally
- The `review_reason` string explains why (e.g., "Location string could not be extracted")

---

## 5. Partial failure handling

The AI Service always returns HTTP 200. Check the `errors` array:

```python
result = await call_ai_service(report)

if result["errors"]:
    logger.warning(f"AI pipeline partial failure for report {report_id}: {result['errors']}")
    # Continue processing with whatever data is available
    # Never fail the ingest because of AI service errors

if result["extracted"] is None:
    # Extraction failed — create incident with minimal data
    # severity engine will run with empty keywords → Low severity
    pass

if result["match"] is None and not result["errors"]:
    # Clean no-match — create new incident
    pass
```

---

## 6. WebSocket broadcast timing

After updating the incident (create or merge), broadcast via `ws/incidents` within 1 second.
The AI Service call is async — do not wait for it before returning HTTP 201 to the caller.

Sequence:
1. `POST /reports` received
2. Persist raw report → return HTTP 201 immediately
3. Fire async task: call AI Service + Geo Service in parallel
4. When both return: update incident → broadcast WebSocket event
