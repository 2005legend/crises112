"""
POST /ai/fuse-report — unified pipeline endpoint.
Routes: voice → STT → extract → dedup
        image → vision (full schema) → extract → dedup
        text  → extract → dedup

Returns full structured response including:
- vision analysis (scene_type, severity_indicators, victims, hazards, etc.)
- extracted text fields
- dedup decision with richer merge_reason
- review_flag for low-confidence results
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from ai_service.engines.stt_engine import STTEngine
from ai_service.engines.vision_engine import VisionEngine
from ai_service.engines.extraction_engine import ExtractionEngine, GROQ_API_KEY
from ai_service.engines.dedup_engine import DedupEngine

logger = logging.getLogger(__name__)
router = APIRouter()


class FuseResponse(BaseModel):
    # STT output
    transcript: Optional[str] = None
    stt_language: Optional[str] = None

    # Vision output — full rich schema
    vision_analysis: Optional[dict] = None

    # Extraction output
    extracted: Optional[dict] = None

    # Dedup output
    match: Optional[str] = None
    similarity_score: Optional[float] = None
    combined_score: Optional[float] = None
    merge_reason: Optional[str] = None
    threshold_used: Optional[float] = None

    # Quality flags
    review_flag: bool = False
    review_reason: Optional[str] = None

    # Pipeline errors
    errors: list[str] = []


@router.post(
    "/fuse-report",
    response_model=FuseResponse,
    summary="Full AI pipeline: STT/Vision → Extract → Dedup",
)
async def fuse_report(
    request: Request,
    modality: str = Form(..., description="voice | text | image"),
    text: Optional[str] = Form(None, description="Raw text (required for text modality)"),
    candidates_json: Optional[str] = Form(
        None, description="JSON array of candidate incidents for dedup"
    ),
    file: Optional[UploadFile] = File(
        None, description="Audio file (voice) or image file (image)"
    ),
):
    """
    Unified AI pipeline. Accepts modality + content, runs the full chain,
    returns structured extraction + vision analysis + dedup decision.

    - voice: file → STT → extract → dedup
    - image: file → vision (full schema) → extract (from actionable_summary) → dedup
    - text:  text → extract → dedup
    """
    if modality not in ("voice", "text", "image"):
        raise HTTPException(
            status_code=400, detail="modality must be one of: voice, text, image"
        )

    models = request.app.state.models
    errors: list[str] = []
    response = FuseResponse()
    working_text: Optional[str] = None
    incident_type_hint: Optional[str] = None  # passed to dedup for dynamic threshold

    # ── Stage 1: Modality processing ─────────────────────────────────────────

    if modality == "voice":
        if file is None:
            raise HTTPException(status_code=400, detail="file is required for voice modality")
        try:
            audio_bytes = await file.read()
            stt = STTEngine(models.stt_model)
            stt_result = stt.transcribe(audio_bytes, filename=file.filename or "audio.wav")
            response.transcript = stt_result["transcript"]
            response.stt_language = stt_result["language_detected"]
            working_text = stt_result["transcript"]
        except Exception as e:
            errors.append(f"stt: {e}")
            logger.error(f"STT stage failed: {e}")

    elif modality == "image":
        if file is None:
            raise HTTPException(status_code=400, detail="file is required for image modality")
        try:
            image_bytes = await file.read()
            vision = VisionEngine()
            vision_result = await vision.caption(image_bytes)
            response.vision_analysis = vision_result

            # Use actionable_summary as working text for extraction
            working_text = vision_result.get("actionable_summary", "")

            # Carry incident_type hint from vision for dynamic dedup threshold
            incident_type_hint = vision_result.get("scene_type")

            # Flag low-confidence vision results
            if vision_result.get("confidence", 1.0) < 0.7:
                response.review_flag = True
                response.review_reason = (
                    f"Vision confidence {vision_result.get('confidence'):.2f} below 0.70 — "
                    "operator verification recommended"
                )
        except Exception as e:
            errors.append(f"vision: {e}")
            logger.error(f"Vision stage failed: {e}")

    elif modality == "text":
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="text is required for text modality")
        working_text = text

    # ── Stage 2: Text extraction ──────────────────────────────────────────────

    if working_text and working_text.strip():
        try:
            ext = ExtractionEngine(api_key=GROQ_API_KEY)
            extracted = ext.extract(working_text)
            response.extracted = extracted

            # Carry incident_type for dedup threshold (text/voice path)
            if not incident_type_hint:
                incident_type_hint = extracted.get("incident_type")

            # Merge review flags from extraction
            if extracted.get("review_flag"):
                response.review_flag = True
                existing = response.review_reason or ""
                ext_reason = extracted.get("review_reason", "")
                response.review_reason = "; ".join(filter(None, [existing, ext_reason]))

        except Exception as e:
            errors.append(f"extraction: {e}")
            logger.error(f"Extraction stage failed: {e}")

    # ── Stage 3: Semantic dedup ───────────────────────────────────────────────

    dedup_summary = None
    if response.extracted:
        dedup_summary = response.extracted.get("summary") or working_text
    elif response.vision_analysis:
        dedup_summary = response.vision_analysis.get("actionable_summary") or working_text
    else:
        dedup_summary = working_text

    if dedup_summary and models.embedding_model is not None:
        try:
            candidates = []
            if candidates_json:
                raw = json.loads(candidates_json)
                candidates = raw  # pass full objects including updated_at, distance_m

            from datetime import datetime, timezone
            report_time = datetime.now(timezone.utc)

            # Get location_string for entity boost
            location_string = None
            if response.extracted:
                location_string = response.extracted.get("location_string")
            elif response.vision_analysis:
                env = response.vision_analysis.get("environment", {})
                location_string = env.get("landmark_visible")

            dedup = DedupEngine(models.embedding_model)
            dedup_result = dedup.find_match(
                summary=dedup_summary,
                candidates=candidates,
                incident_type=incident_type_hint,
                raw_text=working_text,
                report_time=report_time,
                location_string=location_string,
            )
            response.match = dedup_result["match"]
            response.similarity_score = dedup_result["similarity_score"]
            response.combined_score = dedup_result.get("combined_score")
            response.merge_reason = dedup_result["merge_reason"]
            response.threshold_used = dedup_result.get("threshold_used")
        except Exception as e:
            errors.append(f"dedup: {e}")
            logger.error(f"Dedup stage failed: {e}")

    response.errors = errors
    return response
