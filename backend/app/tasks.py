from celery import Celery
import os
import pdfplumber
import pandas as pd
from time import sleep
from app.config import OPENAI_API_KEY
from app.services.db import SessionLocal
from app.models.report import Report
from openai import OpenAI, OpenAIError, RateLimitError

from app.parsers import report_collection as rc
from sqlalchemy.exc import IntegrityError

openai_client = OpenAI(api_key=OPENAI_API_KEY)

celery_app = Celery('tasks', broker='redis://redis:6379/0')

@celery_app.task
def preprocess_report(report_id: int):
    session = SessionLocal()
    try:
        report = session.get(Report, report_id)
        if not report:
            return

        # Обновляем статус на processing
        report.status = 'processing'
        session.commit()

        filepath = f"uploads/{report_id}_{report.filename}"
        ext = report.filename.lower().rsplit('.', 1)[-1]
        raw_text = ''

        if ext == 'pdf':
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    raw_text += page.extract_text() or ''
        elif ext == 'csv':
            df = pd.read_csv(filepath)
            raw_text = df.to_csv(index=False)
        elif ext in ('xls', 'xlsx'):
            df = pd.read_excel(filepath)
            raw_text = df.to_csv(index=False)
        else:
            report.status = 'unsupported'
            session.commit()
            return

        prompt_prefix = (
            "Смотри: ты делаешь формальный финансовый анализ PDF-отчёта. "
            "Ответ — только вывод анализа, без пояснений. Текст отчета ниже:\n\n"
        )
        MAX_CHARS = 15000
        available_chars = MAX_CHARS - len(prompt_prefix)

        chunks = [
            raw_text[i: i + available_chars]
            for i in range(0, len(raw_text), available_chars)
        ]

        analysis_parts = []
        for idx, chunk in enumerate(chunks, start=1):
            piece = chunk + (
                "" if len(chunk) < available_chars else "\n\n[Часть отчёта обрезана]"
            )
            final_prompt = prompt_prefix + piece

            try:
                resp = openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": final_prompt}]
                )
            except (OpenAIError, RateLimitError):
                report.status = 'failed'
                session.commit()
                return

            answer = resp.choices[0].message.content or ""
            analysis_parts.append(answer.strip())

            # Сохраняем промежуточный результат в БД
            report.analysis = "\n\n".join(analysis_parts)
            session.commit()

            # Пауза перед следующим запросом
            if idx < len(chunks):
                sleep(30)

        # Финальное обновление
        report.status = 'processed'
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

@celery_app.task
def fetch_and_store_report(org_id: str, report_id: str):
    """
    1. Находит download_url
    2. Скачивает PDF
    3. Создаёт запись Report (status='downloaded')
    4. Запускает preprocess_report
    """
    session = SessionLocal()
    try:
        # 1. Получить список отчётов и нужный URL
        reports = rc.list_reports(org_id)
        target = next((r for r in reports if r["report_id"] == report_id), None)
        if not target:
            raise ValueError("report_id not found for this organization")

        pdf_path = rc.download_pdf(target["download_url"], "/app/uploads")

        # 2. Создать Report в БД
        rep = Report(
            filename=os.path.basename(pdf_path),
            status="downloaded",
            analysis=None,
        )
        session.add(rep)
        session.commit()
        session.refresh(rep)

        # 3. Переименовать файл «по вашей схеме»
        final_path = f"/app/uploads/{rep.id}_{rep.filename}"
        os.rename(pdf_path, final_path)

        # 4. Запустить дальнейшую обработку
        preprocess_report.delay(rep.id)
        return rep.id

    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


