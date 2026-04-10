"""
Vision Engine — LLaVA image captioning via Ollama.
Focuses on emergency-relevant content. Graceful fallback if ollama unavailable.
"""
import base64
import logging
import time
from engines.utils import log_latency

logger = logging.getLogger(__name__)

EMERGENCY_PROMPT = (
    "You are an emergency response assistant. Analyze this image and describe "
    "only what is relevant to emergency response: injuries, number of people affected, "
    "vehicles involved, fire or smoke, crowd size, visible location landmarks, "
    "and any hazards. If there is no emergency-relevant content, say so plainly. "
    "Do not fabricate emergency details. "
    "Respond with two parts separated by '---ENTITIES---': "
    "first a concise caption (1-3 sentences), then a comma-separated list of detected entities."
)


def caption_image(image_bytes: bytes, filename: str) -> dict:
    """
    Caption an image using LLaVA via Ollama.

    Returns:
        {"caption": str, "entities": list[str]}
    Falls back gracefully if ollama is unavailable.
    """
    start = time.perf_counter()

    try:
        import ollama

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        response = ollama.chat(
            model="llava",
            messages=[
                {
                    "role": "user",
                    "content": EMERGENCY_PROMPT,
                    "images": [image_b64],
                }
            ],
        )

        raw = response["message"]["content"].strip()
        log_latency("vision", start)

        if "---ENTITIES---" in raw:
            parts = raw.split("---ENTITIES---", 1)
            caption = parts[0].strip()
            entities_raw = parts[1].strip()
            entities = [e.strip() for e in entities_raw.split(",") if e.strip()]
        else:
            caption = raw
            entities = []

        return {"caption": caption, "entities": entities}

    except Exception as exc:
        logger.warning("Vision captioning failed (ollama unavailable or error): %s", exc)
        return {
            "caption": "Image received but vision model is currently unavailable.",
            "entities": [],
        }
