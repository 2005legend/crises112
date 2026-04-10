# services/normalizer.py

INCIDENT_TYPE_MAP = {
    "bike crash": "road accident",
    "car crash": "road accident",
    "collision": "road accident",
    "road mishap": "road accident",
    "accident": "road accident",

    "fire breakout": "fire",
    "fire accident": "fire",
    "building fire": "fire",

    "robbery": "crime",
    "theft": "crime",
    "snatching": "crime"
}

def normalize_incident_type(text: str) -> str:
    text = text.lower().strip()

    for key in INCIDENT_TYPE_MAP:
        if key in text:
            return INCIDENT_TYPE_MAP[key]

    return text  # fallback (if unknown)