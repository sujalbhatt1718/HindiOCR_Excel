"""Table detection and reconstruction.

Two complementary strategies are used:

1. **Ruled-table detection** (OpenCV): detect horizontal & vertical lines,
   build a grid of cells, crop each cell and OCR it individually. This is the
   preferred path for documents with visible table borders (forms, bank
   statements, government records).

2. **Layout clustering** (fallback): when a document has few/no ruling lines,
   run full-page OCR and cluster the detected words into rows and columns using
   their geometry. Blank cells are preserved.

The result is always a rectangular row-major list of strings.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.services.ocr_service import OCRService, OCRWord
from app.services.preprocessing_service import PreprocessingService
from app.utils.logger import logger


def _cluster_positions(values: list[float], gap: float) -> list[float]:
    """Cluster sorted 1-D positions; return the mean of each cluster.

    Positions closer than ``gap`` are merged into the same cluster.
    """
    if not values:
        return []
    values = sorted(values)
    clusters: list[list[float]] = [[values[0]]]
    for v in values[1:]:
        if v - clusters[-1][-1] <= gap:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [float(np.mean(c)) for c in clusters]


class TableService:
    """Detect a table and return its reconstructed cell matrix."""

    def __init__(
        self,
        ocr: OCRService,
        preprocessor: PreprocessingService | None = None,
    ) -> None:
        self.ocr = ocr
        self.pre = preprocessor or PreprocessingService()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def extract(
        self, image: np.ndarray, lang: str | None = None
    ) -> tuple[list[list[str]], float]:
        """Detect and reconstruct the table in ``image``.

        Returns ``(rows, confidence)`` where ``rows`` is a rectangular matrix
        of strings and ``confidence`` is the mean OCR confidence (0-1).
        """
        prepared = self.pre.prepare_for_detection(image)
        binary = self.pre.binarize_for_lines(prepared)

        h_lines, v_lines = self._detect_lines(binary)
        rows = self._lines_to_row_bands(h_lines, prepared.shape[0])
        cols = self._lines_to_col_bands(v_lines, prepared.shape[1])

        if len(rows) >= 2 and len(cols) >= 2:
            logger.info("Ruled-table grid detected: {}x{}", len(rows) - 1,
                        len(cols) - 1)
            table, conf = self._extract_grid(prepared, rows, cols, lang)
            if table and any(any(c for c in r) for r in table):
                return self._normalize(table), conf
            logger.info("Grid produced empty cells; using layout clustering")

        logger.info("Using layout-clustering table reconstruction")
        words = self.ocr.ocr_page(prepared, lang)
        table, conf = self._cluster_words(words)
        return self._normalize(table), conf

    # ------------------------------------------------------------------ #
    # Ruled-table detection
    # ------------------------------------------------------------------ #
    def _detect_lines(
        self, binary: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return binary masks of horizontal and vertical table lines."""
        h, w = binary.shape[:2]
        h_size = max(10, w // 30)
        v_size = max(10, h // 30)

        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_size, 1))
        h_lines = cv2.erode(binary, h_kernel, iterations=1)
        h_lines = cv2.dilate(h_lines, h_kernel, iterations=1)

        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_size))
        v_lines = cv2.erode(binary, v_kernel, iterations=1)
        v_lines = cv2.dilate(v_lines, v_kernel, iterations=1)

        return h_lines, v_lines

    def _lines_to_row_bands(
        self, h_lines: np.ndarray, height: int
    ) -> list[float]:
        """Convert the horizontal-line mask into sorted row separator y-values."""
        row_sums = np.sum(h_lines > 0, axis=1)
        threshold = 0.3 * h_lines.shape[1]
        ys = [float(y) for y, s in enumerate(row_sums) if s > threshold]
        bands = _cluster_positions(ys, gap=max(8.0, height * 0.01))
        return bands

    def _lines_to_col_bands(
        self, v_lines: np.ndarray, width: int
    ) -> list[float]:
        """Convert the vertical-line mask into sorted column separator x-values."""
        col_sums = np.sum(v_lines > 0, axis=0)
        threshold = 0.3 * v_lines.shape[0]
        xs = [float(x) for x, s in enumerate(col_sums) if s > threshold]
        bands = _cluster_positions(xs, gap=max(8.0, width * 0.01))
        return bands

    def _extract_grid(
        self,
        image: np.ndarray,
        rows: list[float],
        cols: list[float],
        lang: str | None,
    ) -> tuple[list[list[str]], float]:
        """Crop each grid cell and OCR it individually."""
        table: list[list[str]] = []
        confs: list[float] = []
        pad = 2
        for r in range(len(rows) - 1):
            y0 = int(rows[r]) + pad
            y1 = int(rows[r + 1]) - pad
            row_cells: list[str] = []
            for c in range(len(cols) - 1):
                x0 = int(cols[c]) + pad
                x1 = int(cols[c + 1]) - pad
                if y1 - y0 < 6 or x1 - x0 < 6:
                    row_cells.append("")
                    continue
                cell = image[y0:y1, x0:x1]
                enhanced = self.pre.enhance_cell(cell)
                text, conf = self.ocr.ocr_cell(enhanced, lang)
                row_cells.append(text)
                if text:
                    confs.append(conf)
            table.append(row_cells)
        mean_conf = float(np.mean(confs)) if confs else 0.0
        return table, mean_conf

    # ------------------------------------------------------------------ #
    # Layout clustering fallback
    # ------------------------------------------------------------------ #
    def _cluster_words(
        self, words: list[OCRWord]
    ) -> tuple[list[list[str]], float]:
        """Cluster free-floating OCR words into a row/column matrix."""
        if not words:
            return [], 0.0

        heights = [
            max(p[1] for p in w.box) - min(p[1] for p in w.box) for w in words
        ]
        median_h = float(np.median(heights)) or 10.0

        # --- Group into rows by vertical proximity of centres. ---
        words_sorted = sorted(words, key=lambda w: w.cy)
        rows: list[list[OCRWord]] = [[words_sorted[0]]]
        for w in words_sorted[1:]:
            if abs(w.cy - np.mean([x.cy for x in rows[-1]])) <= median_h * 0.7:
                rows[-1].append(w)
            else:
                rows.append([w])

        # --- Determine global column boundaries from word left edges. ---
        lefts = [min(p[0] for p in w.box) for w in words]
        col_positions = _cluster_positions(lefts, gap=median_h * 1.2)
        if not col_positions:
            col_positions = [0.0]

        def col_index(word: OCRWord) -> int:
            left = min(p[0] for p in word.box)
            return int(np.argmin([abs(left - c) for c in col_positions]))

        # --- Populate the matrix. ---
        table: list[list[str]] = []
        confs: list[float] = []
        for row in rows:
            cells = [""] * len(col_positions)
            for w in sorted(row, key=lambda x: x.cx):
                idx = col_index(w)
                cells[idx] = (cells[idx] + " " + w.text).strip() if cells[idx] \
                    else w.text
                confs.append(w.confidence)
            table.append(cells)

        mean_conf = float(np.mean(confs)) if confs else 0.0
        return table, mean_conf

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize(table: list[list[str]]) -> list[list[str]]:
        """Pad all rows to equal width and drop fully-empty trailing rows."""
        if not table:
            return []
        width = max((len(r) for r in table), default=0)
        norm = [list(r) + [""] * (width - len(r)) for r in table]
        # Drop leading/trailing fully-empty rows.
        while norm and not any(cell.strip() for cell in norm[0]):
            norm.pop(0)
        while norm and not any(cell.strip() for cell in norm[-1]):
            norm.pop()
        # Drop fully-empty columns.
        if norm:
            keep = [
                c for c in range(len(norm[0]))
                if any(row[c].strip() for row in norm)
            ]
            if keep:
                norm = [[row[c] for c in keep] for row in norm]
        return norm
