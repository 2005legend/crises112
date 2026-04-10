"""
POST /extract — Groq Llama-3.3 structured field extraction endpoint.
Accepts raw text. Returns structured incident fields as JSON.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ai_service.engines.extraction_engine import ExtractionEngine

router = APIRouter()
_engine = ExtractionEngine()


class ExtractionRequest(BaseModel):
    text: str


class ExtractionResponse(BaseModel):
    incident_type: Optional[str] = None
    location_string: Optional[str] = None
    time_reference: Optional[str] = None
    victim_count: Optional[int] = None
    risk_keywords: list[str] = []
    summary: str = ""


@router.post("", response_model=ExtractionResponse, summary="Extract structured fields from report text")
async def extract(body: ExtractionRequest):
    """
    Extract incident_type, location_string, time_reference, victim_count,
    risk_keywords, and summary from raw emergency report text using Groq Llama-3.3.
    Fields are null when undeterminable. Returns HTTP 422 on schema validation failure.
    """
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="text field must not be empty")

    try:
        result = _engine.extract(body.text)
        return ExtractionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
