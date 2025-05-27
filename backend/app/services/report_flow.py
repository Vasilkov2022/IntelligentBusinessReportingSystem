# app/services/report_flow.py
import os
from .db import SessionLocal
from ..models.report import Report
from ..parsers import report_collection as rc
from ..tasks import preprocess_report

def create_report_and_start_task(org_id: str, report_id: str) -> int:
    """
    * скачивает PDF,
    * создаёт запись Report,
    * запускает preprocess_report в Celery,
    * возвращает внутренний report_id.
    """
    session = SessionLocal()
    try:
        # 1. найти URL
        reports = rc.list_reports(org_id)
        target  = next((r for r in reports if r["report_id"] == report_id), None)
        if not target:
            raise ValueError("report_id not found")

        # 2. скачать PDF
        pdf_path = rc.download_pdf(target["download_url"], "/app/uploads")

        # 3. записать в БД
        rep = Report(filename=os.path.basename(pdf_path),
                     status="downloaded",
                     analysis=None)
        session.add(rep); session.commit(); session.refresh(rep)

        # 4. переименовать файл
        final = f"/app/uploads/{rep.id}_{rep.filename}"
        os.rename(pdf_path, final)

        # 5. тяжёлая обработка — в Celery
        preprocess_report.delay(rep.id)

        return rep.id
    finally:
        session.close()