from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Report(BaseModel):
    id: Optional[str] = Field(None, alias="_id")

    raw_text: Optional[str] = None
    source: str = "text"
    modality: str = "text"

    file_name: Optional[str] = None

    created_at: Optional[datetime] = None

    class Config:
        populate_by_name = True