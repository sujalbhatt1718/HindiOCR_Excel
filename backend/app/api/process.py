"""Processing endpoint: OCR + table reconstruction."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from app.dependencies import get_document_service
from app.models.schemas import ProcessRequest, ProcessResponse
from app.services.document_service import DocumentService
from app.utils.exceptions import FileNotFoundAppError
from app.utils.helpers import find_upload
from app.utils.logger import logger

router = APIRouter(tags=["process"])


@router.post("/process", response_model=ProcessResponse, summary="Run OCR")
async def process_file(
    payload: ProcessRequest,
    documents: DocumentService = Depends(get_document_service),
) -> ProcessResponse:
    """Process a previously uploaded file into an editable table.

    The heavy OCR work runs in a worker thread so the event loop stays free.
    """
    path = find_upload(payload.file_id)
    if path is None:
        raise FileNotFoundAppError(f"No upload found for id '{payload.file_id}'")

    logger.info("Processing request for file_id={}", payload.file_id)
    result = await run_in_threadpool(
        documents.process, path, payload.file_id, payload.lang
    )
    return result
