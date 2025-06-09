from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel

from ..parsers import report_collection as rc
from .schemas_company import CompanyOut, ParsedReport
from ..tasks import fetch_and_store_report
from ..services.report_flow import create_report_and_start_task

router = APIRouter(prefix="/companies", tags=["parser"])


class SearchBody(BaseModel):
    prefix: str

def _filter(companies, prefix: str) -> list:
    p = prefix.casefold()

    def get_name(item):
        if isinstance(item, dict):
            return item.get("name")
        return getattr(item, "name", None)

    return [
        c for c in companies
        if (name := get_name(c))                     # имя существует
        and isinstance(name, str)
        and name.casefold().startswith(p)            # сравниваем без учёта регистра
    ]

@router.get("", response_model=List[CompanyOut])
async def get_companies(
    prefix: Optional[str] = Query(None, min_length=1, description="Фильтр по префиксу"),
):
    companies = rc.list_companies()
    return _filter(companies, prefix) if prefix else companies


@router.get("/{org_id}/reports", response_model=List[ParsedReport])
async def get_company_reports(org_id: str):
    return rc.list_reports(org_id)


class FetchRequest(BaseModel):
    org_id: str
    report_id: str
    prompt: str


@router.post("/fetch", status_code=202)
async def fetch_report(body: FetchRequest):
    try:
        rep_id = create_report_and_start_task(body.org_id, body.report_id, body.prompt)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error")
    return {"report_id": rep_id}