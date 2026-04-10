from pydantic import BaseModel

class ReportInput(BaseModel):
    text: str
    source: str = "text"