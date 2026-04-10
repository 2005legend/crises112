from db.database import links_col
from datetime import datetime


def link_report(report_id: str, incident_id: str):
    
    if not report_id or not incident_id:
        raise ValueError("report_id and incident_id are required")

    # Prevent duplicate links (IMPORTANT)
    existing = links_col.find_one({
        "report_id": report_id,
        "incident_id": incident_id
    })

    if existing:
        return

    links_col.insert_one({
        "report_id": report_id,
        "incident_id": incident_id,
        "created_at": datetime.utcnow()
    })