from pydantic import BaseModel
from typing import List

class AIResponse(BaseModel):
    location_text: str
    incident_type: str
    affected: int
    embedding: List[float]