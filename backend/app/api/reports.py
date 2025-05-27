from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from ..services.db import SessionLocal
from ..models.report import Report
from ..models.kpi import KPI as KPIModel

from .schemas import ReportBase, ReportDetail

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/reports", response_model=List[ReportBase])
async def list_reports(db: Session = Depends(get_db)):
    return db.query(Report).all()

@router.get("/reports/{report_id}", response_model=ReportDetail)
async def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report