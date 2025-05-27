from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.services.db import SessionLocal
from app.models.report import Report
from app.tasks import preprocess_report
import shutil

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post('/upload')
async def upload_report(file: UploadFile = File(...), db=Depends(get_db)):
    filename = file.filename
    report = Report(filename=filename)
    db.add(report); db.commit(); db.refresh(report)

    path = f"uploads/{report.id}_{filename}"
    with open(path, 'wb') as f:
        shutil.copyfileobj(file.file, f)

    preprocess_report.delay(report.id)
    return { 'report_id': report.id, 'status': report.status }