"""Health-check endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings
from app.dependencies import get_app_settings, get_ocr_service
from app.models.schemas import HealthResponse
from app.services.ocr_service import OCRService, gpu_available

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health(
    settings: Settings = Depends(get_app_settings),
    ocr: OCRService = Depends(get_ocr_service),
) -> HealthResponse:
    """Report service status, version, OCR readiness and GPU availability."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        ocr_loaded=ocr.is_loaded,
        gpu_available=gpu_available(),
    )
