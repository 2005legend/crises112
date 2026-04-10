from pydantic import BaseModel
from datetime import datetime

class SeverityAudit(BaseModel):
    incident_id: str
    score: int
    reason: str
    timestamp: datetime