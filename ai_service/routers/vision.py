"""
POST /vision — LLaVA image captioning endpoint.
Accepts JPEG/PNG images. Returns emergency-focused caption + entities.
"""
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from pydantic import BaseModel
from ai_service.engines.vision_engine import VisionEngine

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/jpg", "application/octet-stream"}
MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50 MB


class VisionResponse(BaseModel):
    caption: str
    entities: list[str]


@router.post("", response_model=VisionResponse, summary="Caption image for emergency content")
async def caption_image(request: Request, file: UploadFile = File(...)):
    """
    Generate an emergency-focused caption for an uploaded image using LLaVA.
    Returns a factual caption and list of detected entities (injuries, vehicles, etc.).
    """
    image_bytes = await file.read()
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="Image file exceeds 50 MB limit")

    engine = VisionEngine()
    result = await engine.caption(image_bytes)
    return VisionResponse(**result)
