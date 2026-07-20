"""Upload endpoint."""
from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.models.schemas import UploadResponse
from app.services.pdf_service import PDFService
from app.utils.helpers import (
    detect_kind,
    new_file_id,
    sanitize_filename,
    save_upload,
    validate_upload,
)
from app.utils.logger import logger

router = APIRouter(tags=["upload"])
_pdf = PDFService()


@router.post("/upload", response_model=UploadResponse, summary="Upload file")
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    """Accept a JPG/JPEG/PNG image or PDF and store it for processing.

    Returns a ``file_id`` used by the ``/process`` endpoint.
    """
    original = sanitize_filename(file.filename or "upload")
    content = await file.read()
    ext = validate_upload(original, content)

    file_id = new_file_id()
    path = save_upload(content, file_id, ext)
    kind = detect_kind(content) or "image"

    pages = 1
    if kind == "pdf":
        pages = _pdf.page_count(path)

    logger.info("Upload accepted: id={} name={} kind={} pages={}",
                file_id, original, kind, pages)
    return UploadResponse(
        file_id=file_id,
        filename=original,
        kind=kind,
        size_bytes=len(content),
        pages=pages,
    )
