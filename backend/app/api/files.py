"""File preview endpoints used by the workspace UI."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from app.services.pdf_service import PDFService
from app.utils.exceptions import FileNotFoundAppError
from app.utils.helpers import find_upload, get_extension

router = APIRouter(tags=["files"])
_pdf = PDFService()

_IMAGE_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


@router.get("/file/{file_id}", summary="Fetch original upload")
async def get_file(file_id: str) -> Response:
    """Return the raw uploaded image, or the first-page PNG for a PDF."""
    path = find_upload(file_id)
    if path is None:
        raise FileNotFoundAppError(f"No upload found for id '{file_id}'")
    ext = get_extension(path.name)
    if ext == ".pdf":
        png = _pdf.first_page_png(path)
        return Response(content=png, media_type="image/png")
    return FileResponse(path, media_type=_IMAGE_MIME.get(ext, "image/png"))


@router.get("/preview/{file_id}/{page}", summary="Fetch PDF page preview")
async def get_pdf_page(file_id: str, page: int) -> Response:
    """Return a specific 1-based PDF page rendered as PNG."""
    path = find_upload(file_id)
    if path is None:
        raise FileNotFoundAppError(f"No upload found for id '{file_id}'")
    if get_extension(path.name) != ".pdf":
        raise FileNotFoundAppError("Requested file is not a PDF.")

    import fitz

    index = max(1, page) - 1
    with fitz.open(str(path)) as doc:
        if index >= doc.page_count:
            raise FileNotFoundAppError("Page out of range.")
        pix = doc.load_page(index).get_pixmap(
            matrix=fitz.Matrix(100 / 72.0, 100 / 72.0), alpha=False
        )
        return Response(content=pix.tobytes("png"), media_type="image/png")
