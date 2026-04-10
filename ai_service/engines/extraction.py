"""
Extraction Engine — Groq Llama-3.3 structured field extraction.
Uses a fixed versioned prompt. Retries once on malformed JSON.
"""
import json
import logging
import os
import time
from typing import Optional
from engines.utils import log_latency

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You are an emergency incident data extraction assistant.
Extract structured information from the given emergency report text.
You MUST respond with ONLY valid JSON — no markdown, no explanation, no extra text.
The JSON must have exactly these six fields:
- "incident_type": string describing the type of incident, or null if unclear
- "location_string": string with the location mentioned, or null if not mentioned
- "time_reference": string with any time reference mentioned, or null if not mentioned
- "victim_count": integer number of victims/injured/affected people, or null if not mentioned
- "risk_keywords": array of strings listing risk-related keywords found in the text
- "summary": string summarizing the incident in at most 200 characters

Example output:
{
  "incident_type": "road_accident",
  "location_string": "Anna Nagar signal, Chennai",
  "time_reference": "this morning",
  "victim_count": 3,
  "risk_keywords": ["accident", "injured", "vehicle"],
  "summary": "Road accident near Anna Nagar signal with 3 injured persons."
}"""

REQUIRED_FIELDS = {
    "incident_type": (str, type(None)),
    "location_string": (str, type(None)),
    "time_reference": (str, type(None)),
    "victim_count": (int, type(None)),
    "risk_keywords": list,
    "summary": str,
}


def _validate_schema(data: dict) -> dict:
    """Validate and coerce extraction result to match required schema."""
    result = {}
    for field, expected_types in REQUIRED_FIELDS.items():
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
        val = data[field]
        if isinstance(expected_types, tuple):
            if not isinstance(val, expected_types):
                raise ValueError(f"Field '{field}' has wrong type: {type(val)}")
        else:
            if not isinstance(val, expected_types):
                raise ValueError(f"Field '{field}' has wrong type: {type(val)}")
    # Enforce summary max length
    result = {k: data[k] for k in REQUIRED_FIELDS}
    if isinstance(result["summary"], str) and len(result["summary"]) > 200:
        result["summary"] = result["summary"][:200]
    return result


def _call_groq(text: str) -> str:
    """Call Groq API and return raw response string."""
    from groq import Groq
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not set.")
    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract incident fields from this report:\n\n{text}"},
        ],
        temperature=0.0,
        max_tokens=512,
    )
    return completion.choices[0].message.content


def extract_fields(text: str) -> dict:
    """
    Extract structured incident fields from free-form text using Groq Llama-3.3.

    Retries once on malformed JSON. Raises ValueError on second failure.

    Returns:
        dict with keys: incident_type, location_string, time_reference,
                        victim_count, risk_keywords, summary
    """
    start = time.perf_counter()

    for attempt in range(2):
        try:
            raw = _call_groq(text)
            # Strip markdown code fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            data = json.loads(raw)
            result = _validate_schema(data)
            log_latency("extraction", start)
            return result
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning("Extraction attempt %d failed: %s", attempt + 1, exc)
            if attempt == 1:
                raise ValueError(f"Extraction schema validation failed after 2 attempts: {exc}") from exc

    raise ValueError("Extraction failed unexpectedly.")
