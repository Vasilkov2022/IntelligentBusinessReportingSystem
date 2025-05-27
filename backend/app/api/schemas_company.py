from pydantic import BaseModel
from typing import List


class CompanyOut(BaseModel):
    org_id: str
    name: str


class ParsedReport(BaseModel):
    report_id: str
    year: str
    title: str
    download_url: str