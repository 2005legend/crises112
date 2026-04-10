from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class Incident(BaseModel):
    id: Optional[str] = Field(None, alias="_id")

    location: str
    incident_type: str

    severity: str
    severity_score: int

    reports: int
    status: str

    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True