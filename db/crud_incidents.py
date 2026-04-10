from db.database import incidents_col
from datetime import datetime
from bson import ObjectId


def create_incident(data: dict):
    doc = {
        "location": data.get("location_text", "unknown"),
        "incident_type": data.get("incident_type", "unknown"),
        "severity": "LOW",
        "severity_score": 0,
        "reports": 1,
        "status": "active",
        "embedding": data.get("embedding", []),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = incidents_col.insert_one(doc)

    return {
        "id": str(result.inserted_id),
        "location": doc["location"],
        "incident_type": doc["incident_type"],
        "severity": doc["severity"],
        "reports": doc["reports"]
    }


def get_all_incidents():
    data = list(incidents_col.find())
    
    # convert ObjectId → string
    for d in data:
        d["_id"] = str(d["_id"])
    
    return data


def get_incident_by_id(incident_id: str):
    doc = incidents_col.find_one({"_id": ObjectId(incident_id)})
    
    if doc:
        doc["_id"] = str(doc["_id"])
    
    return doc


def update_incident(incident_id: str, updates: dict):
    updates["updated_at"] = datetime.utcnow()

    incidents_col.update_one(
        {"_id": ObjectId(incident_id)},
        {"$set": updates}
    )