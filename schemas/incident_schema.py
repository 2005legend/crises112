from pydantic import BaseModel

class IncidentOut(BaseModel):
    id: str
    location: str
    incident_type: str
    severity: str
    reports: int