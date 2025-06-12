from celery import Celery
import os
import json
import requests, uuid, base64, time
import pdfplumber
import pandas as pd
from time import sleep
from app.config import OPENAI_API_KEY
from app.services.db import SessionLocal
from app.models.report import Report
from openai import OpenAI, OpenAIError, RateLimitError
from app.parsers import report_collection as rc
from sqlalchemy.exc import IntegrityError
from .core.redis import redis
from app.config import settings

GC_CLIENT_ID="3dd776b2-772cf72"
GC_CLIENT_SECRET="M2RkNzc2YjItNjYxNzM2Ng=="
SCOPE = "GIGACHAT_API_PERS"
TIMEOUT = (5, 90)
MODEL = "GigaChat-2-Pro"
SYSTEM_PREFIX = (
    "Ты финансовый аналитик. "
    "Тебе нужно ответить на следующий вопрос, "
    "проанализировав прикреплённый файл.\n\n"
)


openai_client = OpenAI(api_key=OPENAI_API_KEY)

celery_app = Celery('tasks', broker='redis://redis:6379/0')

def is_gigachat_token_valid(token: str) -> bool:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    try:
        r = requests.get(
            f"https://gigachat.devices.sberbank.ru/api/v1/models",
            headers=headers,
            timeout=5,
        )
        return r.status_code == 200
    except requests.RequestException:
        return False

def _request_new_token() -> tuple[str, int]:
    rq_uid = str(uuid.uuid4())
    basic  = base64.b64encode(
        f"{GC_CLIENT_ID}:{GC_CLIENT_SECRET}".encode()
    ).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Authorization": f"Basic {GC_CLIENT_SECRET}",
        "RqUID": "6f4e0bf8-bb6c-44f6-a173-66db07823792",
    }
    # body = urlencode({
    #     "grant_type": "client_credentials",
    #     "scope":      SCOPE,
    # })
    data = {"scope": SCOPE}
    resp = requests.post("https://ngw.devices.sberbank.ru:9443/api/v2/oauth", headers=headers, data=data)
    resp.raise_for_status()
    payload = resp.json()
    token = payload["access_token"]
    expires_at = int(payload.get("expires_at")
                     or time.time() + payload["expires_in"])
    return token, expires_at

def get_valid_gc_token() -> str:
    """
    Читаем token/expiry из Redis (или другой storage) и убеждаемся,
    что он жив. Если нет — берём новый.
    """
    token = redis.get("gc_token")
    expires_at = int(redis.get("gc_exp") or 0)

    if token and expires_at > int(time.time()) + 60:
        return token                         # ещё > 1 мин до истечения

    if token and is_gigachat_token_valid(token):
        return token

    token, expires_at = _request_new_token()
    ttl = expires_at - int(time.time()) - 5
    redis.setex("gc_token", ttl, token)
    redis.setex("gc_exp",   ttl, expires_at)
    return token

def upload_pdf(token: str, report_id: int, filename: str, purpose: str = "general") -> str:
    pdf_path = f"uploads/{report_id}_{filename}"
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    with open(pdf_path, "rb") as f:
        files = {
            "file": (filename, f, "application/pdf"),
            "purpose": (None, purpose),
        }
        resp = requests.post(
            "https://gigachat.devices.sberbank.ru/api/v1/files",
            headers=headers,
            files=files,
            timeout=TIMEOUT,
        )
    resp.raise_for_status()
    return resp.json()["id"]

def ask_gigachat(token: str, file_id: str, question: str,
                 temperature: float = 0.1) -> str:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "model": MODEL,
        "temperature": temperature,
        "messages": [
            {
                "role": "user",
                "content": question,
                "attachments": [file_id],
            }
        ]
    }
    resp = requests.post(
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
        headers=headers,
        data=json.dumps(payload),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

@celery_app.task(bind=True, name="preprocess_report")
def preprocess_report(self, report_id: int, user_prompt: str):
    session = SessionLocal()
    try:
        report = session.get(Report, report_id)
        if not report:
            return

        report.status = 'processing'
        session.commit()

        # 1. token
        token = get_valid_gc_token()
        # 2. upload file
        pdf_path = f"uploads/{report_id}_{report.filename}"
        file_id = upload_pdf(token, report_id, report.filename)
        # 3. chat
        user_prompt =  f"{SYSTEM_PREFIX}{(user_prompt or '').strip()}"
        answer = ask_gigachat(token, file_id, user_prompt)
        # 4. persist
        report.analysis = answer
        report.status = "processed"
        session.commit()

    except requests.HTTPError as e:
        # 401 → сброс токена и retry
        if e.response.status_code == 401 and self.request.retries == 0:
            redis.delete("gc_token")
            redis.delete("gc_exp")
            raise self.retry(exc=e)
        report.status = "failed"
        session.commit()
        raise

    except Exception as exc:
        session.rollback()
        report.status = "failed"
        session.commit()
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


