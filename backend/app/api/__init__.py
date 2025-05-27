from fastapi import APIRouter
from fastapi import APIRouter
from .reports import router as reports_router
from .upload import router as upload_router
from .companies import router as companies_router

router = APIRouter()
router.include_router(upload_router)
router = APIRouter()
router.include_router(upload_router, prefix="")
router.include_router(reports_router, prefix="")
router.include_router(companies_router)

@router.post('/upload')
async def upload_report():
    return {"message": "Загрузка отчета"}