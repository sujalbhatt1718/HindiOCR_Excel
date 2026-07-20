"""Excel export endpoint."""
from __future__ import annotations

import io
import urllib.parse

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import get_excel_service
from app.models.schemas import ExportRequest
from app.services.excel_service import ExcelService
from app.utils.exceptions import ExcelExportError
from app.utils.helpers import sanitize_filename
from app.utils.logger import logger

router = APIRouter(tags=["export"])

_XLSX_MIME = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


@router.post("/export", summary="Export edited table to Excel")
async def export_excel(
    payload: ExportRequest,
    excel: ExcelService = Depends(get_excel_service),
) -> StreamingResponse:
    """Generate a formatted ``.xlsx`` from the (edited) table JSON.

    The file is streamed back to the client as an attachment.
    """
    if not payload.table:
        raise ExcelExportError("The table is empty; nothing to export.")

    data = excel.build_workbook(
        payload.table, sheet_name=payload.sheet_name, header=payload.header
    )
    base = sanitize_filename(payload.filename or "hindi_ocr_export")
    if base.lower().endswith(".xlsx"):
        base = base[:-5]
    filename = f"{base or 'export'}.xlsx"
    quoted = urllib.parse.quote(filename)
    logger.info("Exporting Excel: {} ({} bytes)", filename, len(data))

    headers = {
        "Content-Disposition": (
            f"attachment; filename={filename}; filename*=UTF-8''{quoted}"
        ),
        "Content-Length": str(len(data)),
    }
    return StreamingResponse(
        io.BytesIO(data), media_type=_XLSX_MIME, headers=headers
    )
