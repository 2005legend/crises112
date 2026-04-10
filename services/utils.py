import re
from bson import ObjectId


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return text.strip()


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def merge_locations(loc1, loc2):
    if loc1 == loc2:
        return loc1
    return loc1 or loc2


# CRITICAL: MongoDB serializer
def serialize_mongo(doc):
    if not doc:
        return doc

    if isinstance(doc, list):
        return [serialize_mongo(d) for d in doc]

    if isinstance(doc, dict):
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                doc[key] = str(value)
        return doc

    return doc