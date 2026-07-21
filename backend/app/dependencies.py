"""FastAPI dependency providers wiring the singleton services."""
from __future__ import annotations

from app.config import Settings, get_settings
from app.services.document_service import DocumentService, document_service
from app.services.excel_service import ExcelService
from app.services.ocr_service import OCRService, ocr_service

_excel_service = ExcelService()


def get_app_settings() -> Settings:
    return get_settings()


def get_ocr_service() -> OCRService:
    return ocr_service


def get_document_service() -> DocumentService:
    return document_service


def get_excel_service() -> ExcelService:
    return _excel_service
