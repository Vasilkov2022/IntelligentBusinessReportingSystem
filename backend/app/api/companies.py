from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import List
from pydantic import BaseModel

from ..parsers import report_collection as rc
from .schemas_company import CompanyOut, ParsedReport
from ..tasks import fetch_and_store_report   # см. §4
from ..services.report_flow import create_report_and_start_task

router = APIRouter(prefix="/companies", tags=["parser"])


@router.get("", response_model=List[CompanyOut])
async def get_companies():
    return rc.list_companies()


@router.get("/{org_id}/reports", response_model=List[ParsedReport])
async def get_company_reports(org_id: str):
    return rc.list_reports(org_id)


class FetchRequest(BaseModel):
    org_id: str
    report_id: str


@router.post("/fetch", status_code=202)
async def fetch_report(body: FetchRequest):
    try:
        rep_id = create_report_and_start_task(body.org_id, body.report_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error")
    return {"report_id": rep_id}