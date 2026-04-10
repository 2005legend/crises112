"""
Vision Engine — uses NVIDIA NIM (llama-3.2-11b-vision-instruct) for emergency image analysis.
Returns a rich structured JSON with scene_type, severity_indicators, victims, hazards,
environment, vehicles, responders_present, actionable_summary, and confidence.
"""
import base64
import json
import logging
import time

import requests

logger = logging.getLogger(__name__)

import os

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_VISION_MODEL = "meta/llama-3.2-11b-vision-instruct"

VISION_PROMPT = """You are an emergency incident analyst for India's 112 ERSS system.
Analyze this image and extract the following details in JSON format ONLY.
Do not add any explanation, text, or markdown outside the JSON object.

IMPORTANT RULES:
- Every field listed below is REQUIRED. Never omit a field.
- Use false/null/0 as defaults — do not skip fields.
- moving in victims is REQUIRED: set false if victim appears unconscious or unmoving.
- vehicle_damage in severity_indicators is REQUIRED: assess from visible damage.
- actionable_summary must be 2-3 sentences covering: who is affected, what happened,
  what is missing (responders/resources), and what action is needed next.

Return exactly this structure:
{
  "scene_type": "<road_accident|fire|flood|building_collapse|medical_emergency|violence|crowd_crush|explosion|unknown>",
  "incident_category": "<head_on_collision|bike_vs_truck|pedestrian_hit|multi_vehicle_pileup|vehicle_rollover|vehicle_fire|building_fire|wildfire|electrical_fire|cardiac_arrest|unconscious_person|mass_casualty|riot|drowning|gas_leak|structural_collapse|unknown>",
  "severity_indicators": {
    "fire_present": <true|false>,
    "smoke_visible": <true|false>,
    "blood_visible": <true|false>,
    "structural_damage": "<none|minor|moderate|severe>",
    "vehicle_damage": "<none|minor|moderate|severe>",
    "crowd_size": "<none|small|medium|large>",
    "panic_visible": <true|false>,
    "weapon_visible": <true|false>,
    "water_flooding": <true|false>,
    "explosion_evidence": <true|false>,
    "night_time": <true|false>,
    "visibility_poor": <true|false>
  },
  "victims": {
    "count_estimate": "<0|1-2|3-5|6-10|10+>",
    "on_ground": <true|false>,
    "moving": <true|false>,
    "trapped": <true|false>,
    "children_visible": <true|false>,
    "medical_attention_needed": <true|false>
  },
  "hazards": {
    "fuel_leak": <true|false>,
    "live_wires": <true|false>,
    "road_blockage": <true|false>,
    "building_unstable": <true|false>,
    "chemical_spill": <true|false>,
    "gas_cloud": <true|false>
  },
  "environment": {
    "location_type": "<highway|urban_road|rural_road|building_interior|open_ground|water_body|unknown>",
    "weather": "<clear|rain|fog|storm|unknown>",
    "time_of_day": "<daytime|nighttime|dawn_dusk|unknown>",
    "urban_rural": "<urban|rural|unknown>",
    "landmark_visible": "<string or null>",
    "road_type": "<single_carriageway|dual_carriageway|intersection|flyover|unknown|null>"
  },
  "vehicles": {
    "types_present": ["<car|truck|bus|motorcycle|auto|ambulance|fire_truck|police|unknown>"],
    "count": <integer>,
    "overturned": <true|false>,
    "on_fire": <true|false>,
    "blocking_road": <true|false>
  },
  "responders_present": <true|false>,
  "actionable_summary": "<2-3 sentences: who is affected + what happened + what is missing + what action is needed>",
  "confidence": <float 0.0-1.0>
}"""

# Default safe response when analysis fails
DEFAULT_RESPONSE = {
    "scene_type": "unknown",
    "incident_category": "unknown",
    "severity_indicators": {
        "fire_present": False, "smoke_visible": False, "blood_visible": False,
        "structural_damage": "none", "vehicle_damage": "none", "crowd_size": "none",
        "panic_visible": False, "weapon_visible": False, "water_flooding": False,
        "explosion_evidence": False, "night_time": False, "visibility_poor": False,
    },
    "victims": {
        "count_estimate": "0", "on_ground": False, "moving": False,
        "trapped": False, "children_visible": False, "medical_attention_needed": False,
    },
    "hazards": {
        "fuel_leak": False, "live_wires": False, "road_blockage": False,
        "building_unstable": False, "chemical_spill": False, "gas_cloud": False,
    },
    "environment": {
        "location_type": "unknown", "weather": "unknown", "time_of_day": "unknown",
        "urban_rural": "unknown", "landmark_visible": None, "road_type": None,
    },
    "vehicles": {
        "types_present": [], "count": 0, "overturned": False,
        "on_fire": False, "blocking_road": False,
    },
    "responders_present": False,
    "actionable_summary": "Image received — analysis unavailable.",
    "confidence": 0.0,
}


def compute_severity_from_vision(analysis: dict) -> tuple[int, str, list[dict]]:
    """
    Compute severity score, label, and audit trail from vision analysis output.
    Returns (score: int, label: str, audit: list[dict])
    """
    si = analysis.get("severity_indicators", {})
    victims = analysis.get("victims", {})
    hazards = analysis.get("hazards", {})

    score = 0
    audit = []

    def add(factor, weight, explanation):
        nonlocal score
        score += weight
        audit.append({"factor": factor, "weight": weight, "explanation": explanation})

    if si.get("fire_present"):
        add("fire_present", 30, "Fire detected in image")
    if si.get("explosion_evidence"):
        add("explosion_evidence", 25, "Explosion evidence visible")
    if victims.get("trapped"):
        add("victim_trapped", 25, "Victim(s) appear trapped")
    if not victims.get("moving") and victims.get("on_ground"):
        add("victim_unresponsive", 15, "Victim on ground and not moving — likely unconscious")
    if si.get("blood_visible"):
        add("blood_visible", 10, "Blood visible in image")
    if victims.get("on_ground"):
        add("victim_on_ground", 20, "Victim(s) on ground")
    if si.get("weapon_visible"):
        add("weapon_visible", 20, "Weapon visible in image")
    if si.get("structural_damage") == "severe":
        add("structural_damage_severe", 20, "Severe structural damage visible")

    count = victims.get("count_estimate", "0")
    if count in ("6-10", "10+"):
        add("mass_casualty", 20, f"High victim count estimate: {count}")

    if hazards.get("fuel_leak"):
        add("fuel_leak", 15, "Fuel leak detected — fire risk")
    if victims.get("children_visible"):
        add("children_visible", 15, "Children visible among victims")
    if not analysis.get("responders_present"):
        add("no_responders", 10, "No emergency responders on scene")
    if si.get("panic_visible"):
        add("panic_visible", 5, "Panic visible in crowd")
    if hazards.get("road_blockage"):
        add("road_blockage", 5, "Road blocked by incident")

    score = min(score, 100)

    if score >= 80:   label = "Critical"
    elif score >= 55: label = "High"
    elif score >= 30: label = "Medium"
    else:             label = "Low"

    return score, label, audit


class VisionEngine:
    def __init__(self, api_key: str = NVIDIA_API_KEY):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

    def _call_api(self, image_bytes: bytes) -> dict:
        """Synchronous NVIDIA NIM API call (matches NVIDIA sample code pattern)."""
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        image_data_url = f"data:image/jpeg;base64,{b64_image}"

        payload = {
            "model": NVIDIA_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.1,
            "top_p": 1.0,
            "stream": False,
        }

        response = requests.post(
            NVIDIA_INVOKE_URL,
            headers=self.headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def _parse_response(self, raw_content: str) -> dict:
        """Parse model response, stripping markdown fences if present."""
        content = raw_content.strip()

        # Strip ```json ... ``` or ``` ... ``` wrappers
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines).strip()

        return json.loads(content)

    async def caption(self, image_bytes: bytes) -> dict:
        """
        Analyze an emergency image using NVIDIA NIM.
        Returns the full structured analysis dict.
        Also includes computed severity_score and severity_label.
        """
        start = time.time()
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._call_api, image_bytes)

            raw_content = data["choices"][0]["message"]["content"]
            analysis = self._parse_response(raw_content)

            # Compute severity inline so Role 1 can use it directly
            score, label, audit = compute_severity_from_vision(analysis)
            analysis["severity_score"] = score
            analysis["severity_label"] = label
            analysis["severity_audit"] = audit

            elapsed = round((time.time() - start) * 1000)
            logger.info(
                f"Vision analysis done in {elapsed}ms | "
                f"scene={analysis.get('scene_type')} | "
                f"severity={label}({score}) | "
                f"confidence={analysis.get('confidence')}"
            )
            return analysis

        except requests.HTTPError as e:
            logger.error(f"NVIDIA API error {e.response.status_code}: {e.response.text[:200]}")
            return {**DEFAULT_RESPONSE, "actionable_summary": "Image received — API error."}
        except json.JSONDecodeError as e:
            logger.error(f"Vision JSON parse error: {e}")
            return {**DEFAULT_RESPONSE, "actionable_summary": "Image received — parse error."}
        except Exception as e:
            logger.error(f"Vision captioning failed: {e}")
            return {**DEFAULT_RESPONSE, "actionable_summary": "Image received — processing error."}
