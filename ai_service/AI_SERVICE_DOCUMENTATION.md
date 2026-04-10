# EIFS AI Service — Complete Technical Documentation

**Emergency Intelligence Fusion System — Role 2: AI Pipeline**
Version: 1.0 | Stack: Python 3.14, FastAPI, Groq, NVIDIA NIM, Faster-Whisper, MiniLM

---

## 1. Overview

The AI Service is the intelligence core of EIFS. It runs on port **8001** and is called by the Backend (Role 1) after every raw report is ingested. Its job is to convert noisy, multimodal emergency inputs — voice calls, SMS texts, and images — into clean structured data that the backend can store, deduplicate, and score.

### What it does in one sentence
> Receive a raw emergency report in any format → produce structured incident fields + a dedup decision → return everything in one JSON response.

### Models used

| Component | Model | Where it runs |
|---|---|---|
| Speech-to-Text | Faster-Whisper `medium` | Local CPU (int8 quantized) |
| Vision / Image Analysis | `meta/llama-3.2-11b-vision-instruct` | NVIDIA NIM API |
| Text Extraction | `llama-3.3-70b-versatile` | Groq API |
| Semantic Embeddings | `all-MiniLM-L6-v2` | Local CPU |

---

## 2. System Architecture

```
Backend (Role 1) :8000
        │
        │  POST /ai/fuse-report
        ▼
┌─────────────────────────────────────────────────────┐
│                  AI Service :8001                    │
│                                                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────┐ │
│  │  STT     │   │  Vision  │   │  Text passthrough│ │
│  │ (voice)  │   │ (image)  │   │  (text)          │ │
│  └────┬─────┘   └────┬─────┘   └────────┬─────────┘ │
│       │              │                   │           │
│       └──────────────┴───────────────────┘           │
│                       │                              │
│              working_text (normalized)               │
│                       │                              │
│              ┌────────▼────────┐                     │
│              │  Extraction     │  Groq Llama-3.3     │
│              │  Engine         │  (structured JSON)  │
│              └────────┬────────┘                     │
│                       │                              │
│              ┌────────▼────────┐                     │
│              │  Dedup Engine   │  MiniLM + 4 signals │
│              │  (find_match)   │                     │
│              └────────┬────────┘                     │
│                       │                              │
│              FuseResponse (JSON)                     │
└───────────────────────┬─────────────────────────────┘
                        │
                Backend stores result,
                creates/updates incident,
                broadcasts via WebSocket
```

---

## 3. End-to-End Pipeline Flow

### 3.1 Voice Report Flow

```
1. Backend calls POST /ai/fuse-report
   Form fields: modality="voice", file=<audio.wav>

2. STT Engine (Faster-Whisper medium)
   - Reads audio bytes into memory stream
   - Runs VAD filter to strip silent segments
   - Auto-detects language (English / Hindi / Hinglish)
   - Returns: transcript="Lorry ne bike ko maara Anna Nagar signal ke paas"
              language_detected="hi"

3. Extraction Engine (Groq Llama-3.3)
   - Sends transcript to Groq with few-shot system prompt
   - Returns structured JSON:
     incident_type="road_accident"
     location_string="Anna Nagar signal"
     victim_count=1
     risk_keywords=["injured", "bleeding"]
     summary="Lorry hit bike near Anna Nagar signal, one person fell with bleeding."
     field_confidence={incident_type: 0.95, location_string: 0.90, victim_count: 0.85}

4. Dedup Engine (MiniLM + 4-signal fusion)
   - Encodes extracted summary into 384-dim vector
   - Computes 4-signal score against candidate incidents
   - Returns: match="incident-uuid" or null
              combined_score=0.78
              merge_reason="Merged with incident X | combined 0.78 > threshold 0.65 | ..."

5. FuseResponse returned to Backend:
   {
     "transcript": "Lorry ne bike ko maara...",
     "stt_language": "hi",
     "extracted": { incident_type, location_string, ... },
     "match": "incident-uuid",
     "combined_score": 0.78,
     "merge_reason": "...",
     "review_flag": false,
     "errors": []
   }
```

### 3.2 Image Report Flow

```
1. Backend calls POST /ai/fuse-report
   Form fields: modality="image", file=<accident.jpg>

2. Vision Engine (NVIDIA NIM llama-3.2-11b)
   - Base64 encodes image
   - Sends to NVIDIA NIM with emergency-focused prompt
   - Returns full structured analysis:
     scene_type="road_accident"
     incident_category="pedestrian_hit"
     severity_indicators={blood_visible: true, vehicle_damage: "minor", ...}
     victims={count_estimate: "1-2", on_ground: true, moving: false, ...}
     hazards={fuel_leak: false, road_blockage: false, ...}
     environment={location_type: "urban_road", time_of_day: "daytime", ...}
     vehicles={types_present: ["car"], count: 1, ...}
     responders_present=false
     actionable_summary="Pedestrian struck by car on urban road. Victim on ground, unresponsive with visible bleeding. No responders on scene. Immediate ambulance dispatch required."
     confidence=0.85
     severity_score=55
     severity_label="High"
     severity_audit=[{factor: "victim_unresponsive", weight: 15, ...}, ...]

3. Extraction Engine
   - Runs on actionable_summary text (not raw image)
   - Extracts location_string, incident_type, risk_keywords for dedup

4. Dedup Engine
   - Uses extracted summary + scene_type as incident_type hint
   - Applies lower threshold for fire (0.60) vs violence (0.75)

5. FuseResponse returned:
   {
     "vision_analysis": { full schema with severity_score, severity_audit },
     "extracted": { incident_type, location_string, ... },
     "match": null,
     "review_flag": false,
     "errors": []
   }
```

### 3.3 Text Report Flow

```
1. Backend calls POST /ai/fuse-report
   Form fields: modality="text", text="One man bleeding near junction, no ambulance"

2. Extraction Engine (Groq Llama-3.3)
   - Directly processes text
   - Returns structured fields

3. Dedup Engine
   - Compares against candidate incidents

4. FuseResponse returned (no transcript, no vision_analysis)
```

---

## 4. Component Deep Dives

### 4.1 STT Engine (`engines/stt_engine.py`)

**Model:** Faster-Whisper `medium` (CPU, int8 quantized)
**Size:** ~1.5 GB download, ~300 MB RAM at runtime

**Key features:**
- `beam_size=5` for better accuracy vs `base` model
- `vad_filter=True` — strips silent segments, reduces hallucination on quiet audio
- `language=None` — auto-detects English, Hindi, Hinglish without a hint parameter
- Graceful fallback: returns `{"transcript": "", "language_detected": "unknown"}` on any failure — never crashes the pipeline

**Input:** WAV, MP3, M4A audio bytes (up to 50 MB)
**Output:**
```json
{
  "transcript": "Lorry ne bike ko maara Anna Nagar signal ke paas",
  "language_detected": "hi"
}
```

**Latency:** ~3–8 seconds for 1-minute audio on CPU

---

### 4.2 Vision Engine (`engines/vision_engine.py`)

**Model:** `meta/llama-3.2-11b-vision-instruct` via NVIDIA NIM API
**No local GPU required** — runs entirely as an API call

**Prompt design:**
- Emergency-focused: instructs model to look for injuries, vehicles, fire, blood, crowd size, landmarks
- All fields marked REQUIRED — model cannot omit `moving`, `vehicle_damage`, etc.
- `actionable_summary` must be 2–3 sentences covering: who is affected, what happened, what is missing, what action is needed

**Full output schema:**
```json
{
  "scene_type": "road_accident",
  "incident_category": "pedestrian_hit",
  "severity_indicators": {
    "fire_present": false,
    "smoke_visible": false,
    "blood_visible": true,
    "structural_damage": "none",
    "vehicle_damage": "minor",
    "crowd_size": "small",
    "panic_visible": false,
    "weapon_visible": false,
    "water_flooding": false,
    "explosion_evidence": false,
    "night_time": false,
    "visibility_poor": false
  },
  "victims": {
    "count_estimate": "1-2",
    "on_ground": true,
    "moving": false,
    "trapped": false,
    "children_visible": false,
    "medical_attention_needed": true
  },
  "hazards": {
    "fuel_leak": false,
    "live_wires": false,
    "road_blockage": false,
    "building_unstable": false,
    "chemical_spill": false,
    "gas_cloud": false
  },
  "environment": {
    "location_type": "urban_road",
    "weather": "clear",
    "time_of_day": "daytime",
    "urban_rural": "urban",
    "landmark_visible": null,
    "road_type": "single_carriageway"
  },
  "vehicles": {
    "types_present": ["car"],
    "count": 1,
    "overturned": false,
    "on_fire": false,
    "blocking_road": false
  },
  "responders_present": false,
  "actionable_summary": "Pedestrian struck by car on urban road. Victim on ground, unresponsive with visible bleeding. No responders on scene. Immediate ambulance dispatch required.",
  "confidence": 0.85,
  "severity_score": 55,
  "severity_label": "High",
  "severity_audit": [
    {"factor": "victim_unresponsive", "weight": 15, "explanation": "Victim on ground and not moving — likely unconscious"},
    {"factor": "blood_visible", "weight": 10, "explanation": "Blood visible in image"},
    {"factor": "victim_on_ground", "weight": 20, "explanation": "Victim(s) on ground"},
    {"factor": "no_responders", "weight": 10, "explanation": "No emergency responders on scene"}
  ]
}
```

**Severity scoring (computed inline):**

| Factor | Points | Trigger condition |
|---|---|---|
| fire_present | +30 | Fire visible in image |
| explosion_evidence | +25 | Explosion evidence visible |
| victim_trapped | +25 | Victims appear trapped |
| victim_unresponsive | +15 | on_ground=true AND moving=false |
| blood_visible | +10 | Blood visible |
| victim_on_ground | +20 | Victims on ground |
| weapon_visible | +20 | Weapon visible |
| structural_damage_severe | +20 | Severe structural damage |
| mass_casualty | +20 | count_estimate = "6-10" or "10+" |
| fuel_leak | +15 | Fuel leak detected |
| children_visible | +15 | Children among victims |
| no_responders | +10 | responders_present = false |
| panic_visible | +5 | Panic visible in crowd |
| road_blockage | +5 | Road blocked |

**Score → Label:**
- ≥ 80 → Critical
- 55–79 → High
- 30–54 → Medium
- < 30 → Low

**Latency:** ~3–8 seconds per image (NVIDIA NIM API)

---

### 4.3 Extraction Engine (`engines/extraction_engine.py`)

**Model:** `llama-3.3-70b-versatile` via Groq API
**Prompt version:** v2.0

**Key features:**

**Few-shot examples** — 3 examples in system prompt covering road accident (Hinglish), fire (Hinglish), and medical (English) so the model stays consistent on edge cases.

**Field-level confidence** — model returns confidence per field:
```json
"field_confidence": {
  "incident_type": 0.95,
  "location_string": 0.90,
  "victim_count": 0.85
}
```

**Negation detection** — filters out keywords that appear negated in source text:
- "no fire detected" → `fire` removed from risk_keywords
- "not a weapon" → `weapon` removed from risk_keywords

**Groq retry with exponential backoff:**
- Attempt 1: immediate
- Attempt 2: wait 1 second
- Attempt 3: wait 2 seconds
- Attempt 4: wait 4 seconds
- After 3 retries: raises ValueError → pipeline returns partial result

**Request dedup cache** — last 100 requests cached by SHA256(text). Identical reports return instantly without re-calling Groq.

**review_flag** — set to true when:
- Average field confidence < 0.6
- location_string is null (geocoding will fail)

**Output:**
```json
{
  "incident_type": "road_accident",
  "location_string": "Anna Nagar signal",
  "time_reference": null,
  "victim_count": 1,
  "risk_keywords": ["injured", "bleeding"],
  "summary": "Lorry hit bike near Anna Nagar signal, one person fell with bleeding.",
  "field_confidence": {"incident_type": 0.95, "location_string": 0.90, "victim_count": 0.85},
  "review_flag": false,
  "review_reason": null
}
```

**Supported languages:** English, Hinglish (transliterated Hindi), Tamil-English mixed text

**Latency:** ~500ms–2 seconds per request (Groq API)

---

### 4.4 Dedup Engine (`engines/dedup_engine.py`)

This is the most sophisticated component. It uses **4-signal weighted fusion** instead of simple cosine similarity.

#### Why not just cosine similarity?

| Scenario | Cosine only | 4-signal fusion |
|---|---|---|
| Same event, different words | May miss (0.68 < 0.75) | Catches via geo + keyword |
| Same words, different location | May false-merge (0.82 > 0.75) | Geo score drops it below threshold |
| Old report, same area | May false-merge | Temporal decay drops it |
| Voice vs SMS same event | Inconsistent | Normalized summary encoding fixes it |
| Violence vs violence nearby | False-merge | Higher threshold (0.75) prevents it |

#### The 4 signals

**Signal 1 — Semantic similarity (weight 0.45)**
- Model: `all-MiniLM-L6-v2` (384-dimensional embeddings)
- Encodes **extracted summary**, not raw text — noise-free, normalized
- Falls back to first 200 chars of cleaned raw text if summary is null
- Cached by SHA256(normalize(text)) — identical texts never re-encoded

**Signal 2 — Geo score (weight 0.25)**
- Formula: `e^(-distance_m / 200)` (exponential decay)
- 0m → 1.0, 100m → 0.61, 200m → 0.37, 500m → 0.08
- Returns 0.5 neutral when no coordinates available
- Non-linear: genuinely close reports get a strong boost, borderline 490m reports get almost nothing

**Signal 3 — Keyword overlap (weight 0.15)**
- Jaccard similarity on 25 emergency keywords: fire, crash, injured, blood, weapon, flood, etc.
- Returns 0.5 neutral if neither text has any keywords
- Returns 0.2 penalty if only one side has keywords
- Fast, lightweight — catches obvious matches even when sentence structure differs

**Signal 4 — Temporal score (weight 0.15)**
- Linear decay within 30-minute window
- 0 min apart → 1.0, 15 min → 0.5, 30 min → 0.0
- Returns 0.5 neutral when timestamps unavailable

#### Entity boost (additive, max +0.15)
If two reports share location tokens (e.g., both mention "Anna Nagar"), adds up to +0.15 to the final score. Cannot alone cause a merge.

#### Dynamic thresholds per incident type

| Incident Type | Threshold | Reason |
|---|---|---|
| fire | 0.60 | Fire reports vary wildly in description — be aggressive |
| flood | 0.62 | Flood reports also vary |
| road_accident | 0.65 | Default |
| medical | 0.65 | Default |
| unknown | 0.70 | Cautious on unknown types |
| violence | 0.75 | Conservative — two weapon incidents nearby ≠ same event |
| crime | 0.75 | Conservative |

#### Final score formula
```
final_score = 0.45 * semantic
            + 0.25 * geo
            + 0.15 * keyword
            + 0.15 * temporal
            + entity_boost (additive, max +0.15)
```

#### Output
```json
{
  "match": "incident-uuid-or-null",
  "similarity_score": 0.87,
  "combined_score": 0.78,
  "merge_reason": "Merged with incident abc123 | combined score 0.78 > threshold 0.65 | semantic 0.87 | geo 0.61 | keyword 0.33 | temporal 0.80 | entity boost +0.05 | shared keywords: ['accident', 'injured']",
  "threshold_used": 0.65,
  "signal_breakdown": {
    "semantic": 0.87,
    "geo": 0.61,
    "keyword": 0.33,
    "temporal": 0.80,
    "entity_boost": 0.05,
    "distance_m": 120.0
  }
}
```

**Latency:** ~50–200ms for up to 50 candidates

---

## 5. Unified Fuse Endpoint

### `POST /ai/fuse-report`

The single integration point between the Backend and the AI Service.

**Request (multipart/form-data):**

| Field | Type | Required | Description |
|---|---|---|---|
| modality | string | Yes | `voice`, `text`, or `image` |
| text | string | For text | Raw report text |
| file | binary | For voice/image | Audio or image file |
| candidates_json | string | No | JSON array of candidate incidents for dedup |

**candidates_json format:**
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

**Full response:**
```json
{
  "transcript": "Lorry ne bike ko maara...",
  "stt_language": "hi",
  "vision_analysis": null,
  "extracted": {
    "incident_type": "road_accident",
    "location_string": "Anna Nagar signal",
    "time_reference": null,
    "victim_count": 1,
    "risk_keywords": ["injured", "bleeding"],
    "summary": "Lorry hit bike near Anna Nagar signal, one person fell with bleeding.",
    "field_confidence": {"incident_type": 0.95, "location_string": 0.90, "victim_count": 0.85},
    "review_flag": false,
    "review_reason": null
  },
  "match": "incident-uuid",
  "similarity_score": 0.87,
  "combined_score": 0.78,
  "merge_reason": "Merged with incident abc123 | combined score 0.78 > threshold 0.65 | ...",
  "threshold_used": 0.65,
  "review_flag": false,
  "review_reason": null,
  "errors": []
}
```

**Partial failure behavior:**
- If STT fails → `transcript=null`, `errors=["stt: ..."]`, extraction still runs on empty text
- If vision fails → `vision_analysis=null`, `errors=["vision: ..."]`, pipeline continues
- If extraction fails → `extracted=null`, `errors=["extraction: ..."]`, dedup skipped
- If dedup fails → `match=null`, `errors=["dedup: ..."]`
- **Never returns HTTP 500** — always HTTP 200 with errors array

---

## 6. Other Endpoints

### `GET /ai/health`
Returns model load status and average latency per stage.
```json
{
  "stt":        {"status": "loaded", "avg_latency_ms": 4200},
  "vision":     {"status": "ready",  "avg_latency_ms": 5800},
  "extraction": {"status": "ready",  "avg_latency_ms": 780},
  "embedding":  {"status": "loaded", "avg_latency_ms": 45},
  "dedup":      {"status": "loaded", "avg_latency_ms": 120}
}
```

### `POST /stt`
Standalone STT endpoint. Accepts audio file, returns transcript.

### `POST /vision`
Standalone vision endpoint. Accepts image file, returns full analysis schema.

### `POST /extract`
Standalone extraction endpoint. Accepts `{"text": "..."}`, returns structured fields.

### `POST /dedup`
Standalone dedup endpoint. Accepts summary + candidates, returns match decision.

### `POST /dedup/batch-test`
Evaluation endpoint. Accepts labeled test pairs, returns precision/recall/F1.
```json
{
  "total": 18,
  "correct": 16,
  "precision": 0.92,
  "recall": 0.91,
  "f1": 0.91
}
```

---

## 7. Model Startup

On service startup, the `ModelLoader` loads:
1. **Faster-Whisper medium** — downloads from HuggingFace (~1.5 GB) on first run, cached locally
2. **all-MiniLM-L6-v2** — downloads from HuggingFace (~90 MB) on first run, cached locally
3. **NVIDIA NIM** — no local model, API key only
4. **Groq** — no local model, API key only

Health status tracked per model: `not_loaded` → `loaded` / `error`

---

## 8. Running the Service

```bash
# Install dependencies
pip install -r ai_service/requirements.txt

# Start the service
uvicorn ai_service.main:app --port 8001 --reload

# Run tests (fast, no model downloads)
python -m pytest ai_service/tests/ -v -m "not slow"

# Run with real models (slow tests)
python -m pytest ai_service/tests/ -v -m slow

# Test vision on real images
python ai_service/tests/run_vision_test.py
```

---

## 9. Test Coverage

**51 tests, all passing**

| Test file | What it covers |
|---|---|
| `test_extraction_engine.py` | Schema completeness, null fields, retry logic, negation, PBT Props 1–3 |
| `test_dedup_engine.py` | All 4 signals, dynamic thresholds, entity boost, geo score, PBT Props 4–5 |
| `test_stt_engine.py` | Silent audio, Hindi detection, model=None fallback, multi-segment join |
| `test_fuse_endpoint.py` | All 3 modalities, partial failure, review_flag, response schema |
| `test_stt_live.py` | Real Faster-Whisper medium model load + transcription (marked slow) |
| `test_vision_live.py` | Real NVIDIA NIM API call (marked slow) |
| `test_vision_images.py` | Parametrized test on any images in test_images/ folder |

**Property-based tests (hypothesis):**
- Property 1: Extraction schema always has all 6 required fields
- Property 2: Extraction JSON round-trip is lossless
- Property 3: Malformed extraction always returns HTTP 422
- Property 4: Dedup threshold is strictly enforced (combined > threshold = match)
- Property 5: Low similarity always signals new incident creation

---

## 10. Integration Contract with Backend (Role 1)

The Backend calls `POST /ai/fuse-report` after persisting a raw report. It sends:
- `modality` — from the report record
- `text` or `file` — the raw content
- `candidates_json` — open incidents from the Geo Service proximity query, each with `incident_id`, `summary`, `distance_m`, `updated_at`, `location_string`

The Backend reads back:
- `extracted.incident_type` → stored in `reports.extracted_json`
- `extracted.location_string` → passed to Geo Service for geocoding
- `extracted.risk_keywords` → fed into severity engine
- `match` → if not null, merge report into that incident; if null, create new incident
- `merge_reason` → stored in `incident_reports.merge_reason`
- `vision_analysis.severity_score` → used as initial severity for image reports
- `vision_analysis.severity_audit` → stored in `severity_audit` table
- `review_flag` → stored on report record, shown in dashboard as operator review needed
- `errors` → logged, pipeline continues with partial data

---

## 11. Key Design Decisions

**Why Faster-Whisper medium instead of base?**
Medium has significantly better accuracy on accented English, Hindi, and Hinglish. Base was too inaccurate for real emergency call transcription. The speed tradeoff (~3–8s vs ~1–2s) is acceptable since STT runs async.

**Why NVIDIA NIM instead of Ollama/LLaVA?**
Ollama requires local GPU or is very slow on CPU. NVIDIA NIM gives cloud-grade inference with no local hardware requirement, ~3–8s response time, and the 11B vision model is significantly more capable than LLaVA 7B for structured JSON extraction.

**Why encode extracted summaries instead of raw text for dedup?**
Raw transcripts are noisy — "lorry ne bike ko maara" and "truck hit motorcycle" are the same event but have low cosine similarity on raw text. Extracted summaries are normalized English, so MiniLM can compare them accurately.

**Why exponential geo decay instead of linear?**
Linear decay treats 490m the same as 10m proportionally. Exponential decay (`e^(-d/200)`) gives a strong boost to genuinely close reports (< 100m) and near-zero weight to borderline 400–500m reports, which is the right behavior for urban emergency dispatch.

**Why dynamic thresholds?**
Fire reports use words like "smoke", "flames", "burning", "aag" — all describing the same event but with low semantic similarity. A lower threshold (0.60) catches these. Violence incidents need a higher threshold (0.75) because two separate weapon incidents in the same neighborhood should NOT be merged.
