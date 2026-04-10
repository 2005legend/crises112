"""
Extraction Engine — Groq Llama-3.3 structured field extraction.
Improvements:
- Few-shot examples for road_accident, fire, medical
- Field-level confidence scores
- Groq retry with exponential backoff on rate limits
- Request deduplication cache (last 100 requests)
- Negation detection in risk_keywords
- review_flag on low confidence
"""
import hashlib
import json
import logging
import re
import time
from collections import OrderedDict
from typing import Optional

from groq import Groq, RateLimitError
from pydantic import BaseModel, field_validator, ValidationError

logger = logging.getLogger(__name__)

import os

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
EXTRACTION_MODEL = "llama-3.3-70b-versatile"
EXTRACTION_PROMPT_VERSION = "v2.0"
REQUEST_CACHE_SIZE = 100
LOW_CONFIDENCE_THRESHOLD = 0.6

EXTRACTION_SYSTEM_PROMPT = """You are an emergency incident data extractor for India's 112 ERSS system.
Extract structured information from the given emergency report text.

Return ONLY a valid JSON object with exactly these fields:
{
  "incident_type": "<string or null>",
  "location_string": "<string or null>",
  "time_reference": "<string or null>",
  "victim_count": <integer or null>,
  "risk_keywords": ["<string>", ...],
  "summary": "<string, max 200 characters>",
  "field_confidence": {
    "incident_type": <float 0.0-1.0>,
    "location_string": <float 0.0-1.0>,
    "victim_count": <float 0.0-1.0>
  }
}

Rules:
- Set a field to null if you cannot determine it from the text
- Do NOT guess or hallucinate values
- incident_type: one of "road_accident", "fire", "medical", "crime", "flood", "other", or null
- risk_keywords: extract ONLY keywords actually present — fire, unconscious, weapon, highway, injured, child, bleeding, trapped, explosion
- Do NOT add risk_keywords that are negated (e.g. "no fire" → do NOT add "fire")
- summary: concise factual summary in max 200 characters
- field_confidence: how confident you are in each extracted field (0.0 = guessing, 1.0 = certain)
- Support English, Hinglish (transliterated Hindi), and Tamil-English mixed text
- Return ONLY the JSON object, no explanation

Examples:

Input: "Lorry ne bike ko maara Anna Nagar signal ke paas, ek aadmi gir gaya khoon aa raha hai"
Output: {"incident_type": "road_accident", "location_string": "Anna Nagar signal", "time_reference": null, "victim_count": 1, "risk_keywords": ["injured", "bleeding"], "summary": "Lorry hit bike near Anna Nagar signal, one person fell with bleeding.", "field_confidence": {"incident_type": 0.95, "location_string": 0.9, "victim_count": 0.85}}

Input: "Building mein aag lagi hai T Nagar main road pe, bahut dhuan aa raha hai, log bhaag rahe hain"
Output: {"incident_type": "fire", "location_string": "T Nagar main road", "time_reference": null, "victim_count": null, "risk_keywords": ["fire", "smoke"], "summary": "Building fire on T Nagar main road with heavy smoke, people evacuating.", "field_confidence": {"incident_type": 0.98, "location_string": 0.88, "victim_count": 0.0}}

Input: "Old man collapsed near Silk Board junction, not breathing, no pulse"
Output: {"incident_type": "medical", "location_string": "Silk Board junction", "time_reference": null, "victim_count": 1, "risk_keywords": ["unconscious", "not breathing"], "summary": "Elderly man collapsed near Silk Board junction, unresponsive with no pulse.", "field_confidence": {"incident_type": 0.97, "location_string": 0.92, "victim_count": 0.95}}"""


# Negation patterns — if a keyword is preceded by these, it should be excluded
NEGATION_PATTERN = re.compile(
    r"\b(no|not|without|false|none|didn't|did not|wasn't|was not|no sign of)\s+\w*\s*",
    re.IGNORECASE,
)


def filter_negated_keywords(keywords: list[str], text: str) -> list[str]:
    """Remove keywords that appear negated in the source text."""
    filtered = []
    for kw in keywords:
        pattern = rf"\b(no|not|without|false|none|didn't|did not|wasn't|was not|no sign of)\s+\w*\s*{re.escape(kw)}"
        if not re.search(pattern, text, re.IGNORECASE):
            filtered.append(kw)
    return filtered


class ExtractionResult(BaseModel):
    incident_type: Optional[str] = None
    location_string: Optional[str] = None
    time_reference: Optional[str] = None
    victim_count: Optional[int] = None
    risk_keywords: list[str] = []
    summary: str = ""
    field_confidence: dict = {}

    @field_validator("summary")
    @classmethod
    def truncate_summary(cls, v: str) -> str:
        return v[:200] if v else ""

    @field_validator("victim_count", mode="before")
    @classmethod
    def coerce_victim_count(cls, v):
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None


class ExtractionEngine:
    def __init__(self, api_key: str = GROQ_API_KEY):
        self.client = Groq(api_key=api_key)
        # LRU request dedup cache: sha256(text) → result
        self._request_cache: OrderedDict[str, dict] = OrderedDict()

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.strip().lower().encode()).hexdigest()

    def _get_cached(self, text: str) -> Optional[dict]:
        key = self._cache_key(text)
        if key in self._request_cache:
            logger.debug(f"Extraction cache hit for key {key[:8]}")
            return self._request_cache[key]
        return None

    def _set_cached(self, text: str, result: dict):
        key = self._cache_key(text)
        self._request_cache[key] = result
        # Evict oldest if over limit
        while len(self._request_cache) > REQUEST_CACHE_SIZE:
            self._request_cache.popitem(last=False)

    def _call_groq(self, text: str) -> str:
        """Call Groq API with exponential backoff on rate limits."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=EXTRACTION_MODEL,
                    messages=[
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Emergency report:\n{text}"},
                    ],
                    temperature=0.1,
                    max_tokens=512,
                    response_format={"type": "json_object"},
                )
                return response.choices[0].message.content
            except RateLimitError:
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(f"Groq rate limit hit, retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Groq call failed attempt {attempt + 1}: {e}")
                time.sleep(1)
        raise ValueError("Groq API failed after all retries")

    def extract(self, text: str) -> dict:
        """
        Extract structured fields from report text.
        Returns result dict with review_flag if confidence is low.
        """
        if not text or not text.strip():
            return {**ExtractionResult().model_dump(), "review_flag": False, "review_reason": None}

        # Check request dedup cache
        cached = self._get_cached(text)
        if cached:
            return cached

        start = time.time()
        last_error = None

        for attempt in range(2):
            try:
                raw_json = self._call_groq(text)
                parsed = json.loads(raw_json)
                result = ExtractionResult(**parsed)

                # Apply negation filtering to risk_keywords
                result.risk_keywords = filter_negated_keywords(result.risk_keywords, text)

                elapsed = round((time.time() - start) * 1000)
                logger.info(
                    f"Extraction v{EXTRACTION_PROMPT_VERSION} in {elapsed}ms | "
                    f"type={result.incident_type} | keywords={result.risk_keywords}"
                )

                # Compute review flag
                fc = result.field_confidence
                min_confidence = min(fc.values()) if fc else 1.0
                avg_confidence = sum(fc.values()) / len(fc) if fc else 1.0
                review_flag = avg_confidence < LOW_CONFIDENCE_THRESHOLD or result.location_string is None
                review_reason = None
                if review_flag:
                    reasons = []
                    if avg_confidence < LOW_CONFIDENCE_THRESHOLD:
                        reasons.append(f"Low avg field confidence ({avg_confidence:.2f})")
                    if result.location_string is None:
                        reasons.append("Location string could not be extracted")
                    review_reason = "; ".join(reasons)

                output = {
                    **result.model_dump(),
                    "review_flag": review_flag,
                    "review_reason": review_reason,
                }
                self._set_cached(text, output)
                return output

            except (json.JSONDecodeError, ValidationError, KeyError) as e:
                last_error = e
                logger.warning(f"Extraction attempt {attempt + 1} failed: {e}")
                if attempt == 0:
                    continue

        raise ValueError(f"Extraction failed after 2 attempts: {last_error}")
