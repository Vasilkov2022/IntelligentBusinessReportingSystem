from fastapi import FastAPI
from app.api import router as api_router
from app.services.db import init_db

app = FastAPI(
    title="Business Reporting AI",
    version="0.1.0",
    description="Интеллектуальный сервис анализа отчетности"
)

@app.on_event("startup")
async def on_startup():
    # инициализировать БД при старте (с retry)
    init_db()

app.include_router(api_router, prefix="/api")

@app.get("/health")
async def health_check():
    return {"status": "ok"}