# services/pipeline.py

from db.crud_incidents import create_incident, update_incident, get_all_incidents
from db.crud_links import link_report

from integrations.ai_service import call_ai_service

from services.severity import compute_severity
from services.normalizer import normalize_incident_type
from services.utils import clean_text, safe_int


async def process_report(payload: dict):

    # 1. Get report_id (already created in report.py)
    report_id = payload.get("report_id")

    # 2. Clean input
    payload["text"] = clean_text(payload.get("text", ""))

    # 3. Fetch candidate incidents
    all_incidents = get_all_incidents()

    candidates = [
        {
            "id": str(i["_id"]),
            "location": i.get("location"),
            "incident_type": i.get("incident_type")
        }
        for i in all_incidents
    ]

    # 4. Call AI service
    ai_response = call_ai_service(payload, candidates)

    # 5. Handle AI failure
    if ai_response.get("errors"):
        extracted = {
            "location_text": "unknown",
            "incident_type": "unknown",
            "affected": 0
        }
        match_id = None
    else:
        extracted = ai_response.get("extracted", {})
        match_id = ai_response.get("match")

    # 6. Normalize + sanitize
    extracted["incident_type"] = normalize_incident_type(
        extracted.get("incident_type", "")
    )
    extracted["affected"] = safe_int(extracted.get("affected", 0))

    incident = None

    # 7. Match existing incident
    if match_id:
        incident = next(
            (i for i in all_incidents if str(i["_id"]) == match_id),
            None
        )

        if incident:
            incident["reports"] = incident.get("reports", 1) + 1

            update_incident(incident["_id"], {
                "reports": incident["reports"]
            })

    # 8. Create new incident if needed
    if not incident:
        incident = create_incident({
            "location_text": extracted.get("location_text"),
            "incident_type": extracted.get("incident_type"),
            "affected": extracted.get("affected"),
            "embedding": []
        })

    # 9. Link report → incident (FIXED)
    incident_id_str = str(incident.get("id", incident.get("_id")))
    link_report(report_id, incident_id_str)

    # 10. Compute severity
    severity, score = compute_severity(incident, extracted)

    # 11. Update incident
    update_incident(incident.get("id", incident.get("_id")), {
        "severity": severity,
        "severity_score": score
    })

    # 12. Return incident data
    return {
        "incident_id": incident_id_str,
        "location": incident.get("location"),
        "type": incident.get("incident_type"),
        "severity": severity,
        "reports": incident.get("reports", 1)
    }