"""High-level orchestrator that turns an uploaded file into a table.

Ties together the PDF, preprocessing, OCR and table services and implements the
documented processing pipeline:

    validate -> (PDF? render pages) -> preprocess -> detect table ->
    extract cells -> OCR -> reconstruct -> merge pages
"""
from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

from app.models.schemas import PageResult, ProcessResponse
from app.services.ocr_service import OCRService, ocr_service
from app.services.pdf_service import PDFService
from app.services.preprocessing_service import PreprocessingService
from app.services.table_service import TableService
from app.utils.exceptions import CorruptedFileError, NoTableFoundError
from app.utils.helpers import get_extension
from app.utils.logger import logger
from app.utils.numeral_converter import convert_table


class DocumentService:
    """Process a single stored file end-to-end into a merged table."""

    def __init__(
        self,
        ocr: OCRService | None = None,
        pdf: PDFService | None = None,
        table: TableService | None = None,
    ) -> None:
        self.ocr = ocr or ocr_service
        self.pdf = pdf or PDFService()
        self.pre = PreprocessingService()
        self.table = table or TableService(self.ocr, self.pre)

    def _load_images(self, path: Path) -> list[np.ndarray]:
        """Return a list of BGR page images for the file (1 for images)."""
        ext = get_extension(path.name)
        if ext == ".pdf":
            return self.pdf.render_pages(path)
        data = np.fromfile(str(path), dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if image is None:
            raise CorruptedFileError("Image file could not be decoded.")
        return [image]

    def process(
        self, path: Path, file_id: str, lang: str | None = None
    ) -> ProcessResponse:
        """Run the full pipeline and return a :class:`ProcessResponse`."""
        start = time.perf_counter()
        images = self._load_images(path)
        logger.info("Processing {} ({} page(s))", path.name, len(images))

        pages: list[PageResult] = []
        merged: list[list[str]] = []
        all_confs: list[float] = []
        expected_cols: int | None = None

        for idx, image in enumerate(images, start=1):
            rows, conf = self.table.extract(image, lang)
            # Normalise Hindi numerals to ASCII digits before the table is
            # reconstructed, displayed or exported (Hindi words are preserved).
            rows = convert_table(rows)
            n_rows = len(rows)
            n_cols = len(rows[0]) if rows else 0
            pages.append(
                PageResult(
                    page=idx, rows=rows, n_rows=n_rows,
                    n_cols=n_cols, confidence=round(conf, 4),
                )
            )
            if conf:
                all_confs.append(conf)

            if not rows:
                continue
            # Merge pages, dropping repeated header rows on later pages when the
            # column count matches the first page's table.
            if not merged:
                merged.extend(rows)
                expected_cols = n_cols
            else:
                start_row = 0
                if (
                    expected_cols == n_cols
                    and merged
                    and rows
                    and rows[0] == merged[0]
                ):
                    start_row = 1  # skip duplicated header
                merged.extend(rows[start_row:])

        if not merged:
            raise NoTableFoundError(
                "No readable table or text was detected in the document."
            )

        merged = self._rectangularize(merged)
        overall_conf = float(np.mean(all_confs)) if all_confs else 0.0
        elapsed = time.perf_counter() - start
        logger.info(
            "Processed {} in {:.2f}s -> {}x{} (conf={:.3f})",
            path.name, elapsed, len(merged),
            len(merged[0]) if merged else 0, overall_conf,
        )

        return ProcessResponse(
            file_id=file_id,
            pages=pages,
            table=merged,
            n_rows=len(merged),
            n_cols=len(merged[0]) if merged else 0,
            confidence=round(overall_conf, 4),
            processing_time=round(elapsed, 3),
        )

    @staticmethod
    def _rectangularize(table: list[list[str]]) -> list[list[str]]:
        """Pad all rows to the same width."""
        if not table:
            return []
        width = max(len(r) for r in table)
        return [r + [""] * (width - len(r)) for r in table]


document_service = DocumentService()
