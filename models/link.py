from pydantic import BaseModel

class IncidentReport(BaseModel):
    report_id: str
    incident_id: str