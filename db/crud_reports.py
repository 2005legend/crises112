from db.database import reports_col
from datetime import datetime


def create_report(data: dict):
    doc = {
        "raw_text": data.get("text", ""),
        "source": data.get("source", "text"),
        "modality": data.get("source", "text"),
        "file_name": data.get("filename"),   # optional
        "created_at": datetime.utcnow()
    }

    result = reports_col.insert_one(doc)

    # Always return clean response object
    return {
        "id": str(result.inserted_id),
        "raw_text": doc["raw_text"],
        "source": doc["source"],
        "created_at": doc["created_at"]
    }