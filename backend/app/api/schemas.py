from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ReportBase(BaseModel):
    id: int
    filename: str
    upload_time: datetime
    status: str

    class Config:
        from_attributes = True

class ReportDetail(ReportBase):
    analysis: Optional[str] = None

    class Config:
        from_attributes = True