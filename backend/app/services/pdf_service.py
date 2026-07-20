"""PDF processing: page counting and page-to-image rendering (PyMuPDF)."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.config import settings
from app.utils.exceptions import PDFProcessingError
from app.utils.logger import logger


class PDFService:
    """Render PDF pages to OpenCV BGR images using PyMuPDF (fitz)."""

    def page_count(self, path: str | Path) -> int:
        """Return the number of pages in the PDF."""
        import fitz

        try:
            with fitz.open(str(path)) as doc:
                return doc.page_count
        except Exception as exc:
            raise PDFProcessingError(f"Could not open PDF: {exc}") from exc

    def render_pages(
        self, path: str | Path, dpi: int | None = None
    ) -> list[np.ndarray]:
        """Render each PDF page to a BGR ``np.ndarray``.

        Pages are returned in order. The number of pages is capped by
        ``settings.max_pdf_pages`` to protect against memory exhaustion.
        """
        import fitz

        dpi = dpi or settings.pdf_render_dpi
        images: list[np.ndarray] = []
        try:
            with fitz.open(str(path)) as doc:
                total = doc.page_count
                if total == 0:
                    raise PDFProcessingError("PDF has no pages.")
                limit = min(total, settings.max_pdf_pages)
                if total > limit:
                    logger.warning(
                        "PDF has {} pages; processing first {}", total, limit
                    )
                zoom = dpi / 72.0
                matrix = fitz.Matrix(zoom, zoom)
                for index in range(limit):
                    page = doc.load_page(index)
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                        pix.height, pix.width, pix.n
                    )
                    if pix.n == 4:
                        bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
                    else:
                        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                    images.append(bgr)
                    logger.debug("Rendered PDF page {}/{}", index + 1, limit)
        except PDFProcessingError:
            raise
        except Exception as exc:
            raise PDFProcessingError(f"Failed to render PDF: {exc}") from exc

        if not images:
            raise PDFProcessingError("No pages could be rendered from the PDF.")
        return images

    def first_page_png(self, path: str | Path, dpi: int = 100) -> bytes:
        """Render the first page to PNG bytes (for previews)."""
        import fitz

        try:
            with fitz.open(str(path)) as doc:
                if doc.page_count == 0:
                    raise PDFProcessingError("PDF has no pages.")
                zoom = dpi / 72.0
                pix = doc.load_page(0).get_pixmap(
                    matrix=fitz.Matrix(zoom, zoom), alpha=False
                )
                return pix.tobytes("png")
        except PDFProcessingError:
            raise
        except Exception as exc:
            raise PDFProcessingError(f"Failed to render preview: {exc}") from exc
