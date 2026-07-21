"""Table detection and reconstruction.

The pipeline runs full-page OCR **once** to obtain every word together with its
bounding box, then reconstructs the table from that geometry. Working from word
boxes (rather than re-cropping and re-OCRing each cell) avoids clipping edge glyphs
and is robust to faint or missing borders.

Column and row separators are chosen as follows:

1. **Ruled-table detection** (OpenCV): when a document has clear, regular
   horizontal *and* vertical rulings, those line positions are used directly as
   cell boundaries. This preserves header placement on bordered forms.

2. **Geometry clustering** (default fallback): rows are grouped by the vertical
   proximity of word centres, and columns are derived from whitespace gaps that
   are consistent across rows. This handles screenshots, spreadsheets and scans
   whose internal borders are too faint to detect reliably.

Numeric regions are optionally re-recognised with a Latin-optimised model
because the Devanagari recogniser tends to misread ASCII digits. The result is
always a rectangular row-major list of strings.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.config import settings
from app.services.ocr_service import OCRService, OCRWord
from app.services.preprocessing_service import PreprocessingService
from app.utils.logger import logger
from app.utils.numeral_converter import (
    DEVANAGARI_TO_ASCII,
    has_devanagari_letter,
    is_numeric_like,
)

_DEVANAGARI_DIGIT_CHARS = frozenset(chr(code) for code in DEVANAGARI_TO_ASCII)


def _is_ascii_numeric(text: str) -> bool:
    """True if ``text`` is a clean ASCII number with no Devanagari characters.

    Used to accept an English re-recognition only when it produced genuine
    Latin digits — never when it hallucinated Devanagari characters, or noisy
    letters, from a crop that was actually Hindi.
    """
    if not is_numeric_like(text):
        return False
    if not any(ch.isascii() and ch.isdigit() for ch in text):
        return False
    if has_devanagari_letter(text):
        return False
    return not any(ch in _DEVANAGARI_DIGIT_CHARS for ch in text)


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


def _x_extent(box: list[list[float]]) -> tuple[float, float]:
    xs = [p[0] for p in box]
    return min(xs), max(xs)


def _y_extent(box: list[list[float]]) -> tuple[float, float]:
    ys = [p[1] for p in box]
    return min(ys), max(ys)


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

        words = self.ocr.ocr_page(prepared, lang)
        if not words:
            logger.info("No text detected on page")
            return [], 0.0
        self._refine_numbers(prepared, words)

        # Prefer ruled-line boundaries when the document has a clean grid;
        # otherwise fall back to word-geometry clustering.
        binary = self.pre.binarize_for_lines(prepared)
        h_lines, v_lines = self._detect_lines(binary)
        row_bounds = self._lines_to_row_bands(h_lines, prepared.shape[0])
        col_bounds = self._lines_to_col_bands(v_lines, prepared.shape[1])

        if self._grid_is_usable(row_bounds, col_bounds, words, prepared.shape):
            logger.info(
                "Ruled-table grid: {} rows x {} cols",
                len(row_bounds) - 1, len(col_bounds) - 1,
            )
            table, conf = self._assign_to_grid(words, row_bounds, col_bounds)
        else:
            logger.info("Reconstructing table from word geometry")
            table, conf = self._reconstruct_from_words(words)

        return self._normalize(table), conf

    # ------------------------------------------------------------------ #
    # Numeric refinement
    # ------------------------------------------------------------------ #
    def _refine_numbers(
        self, image: np.ndarray, words: list[OCRWord]
    ) -> None:
        """Re-recognise numeric-looking words with the Latin digit model.

        Mutates ``words`` in place. Only words that look numeric and contain no
        Devanagari *letters* are candidates, so Hindi words are never touched.
        The re-recognised text is kept only when it is confidently numeric.
        """
        if not settings.ocr_refine_numbers:
            return
        h, w = image.shape[:2]
        for word in words:
            if has_devanagari_letter(word.text) or not is_numeric_like(
                word.text
            ):
                continue
            (x0, x1), (y0, y1) = _x_extent(word.box), _y_extent(word.box)
            pad = 4
            xa, xb = max(0, int(x0) - pad), min(w, int(x1) + pad)
            ya, yb = max(0, int(y0) - pad), min(h, int(y1) + pad)
            if xb - xa < 4 or yb - ya < 4:
                continue
            crop = image[ya:yb, xa:xb]
            text, conf = self.ocr.recognize_region(
                crop, settings.ocr_digit_lang
            )
            # Only trust the Latin re-read when it is confidently ASCII-numeric
            # and at least as confident as the original; otherwise a genuine
            # Devanagari numeral (which English cannot read) would be corrupted.
            if (
                text
                and conf >= settings.ocr_digit_min_conf
                and conf >= word.confidence
                and _is_ascii_numeric(text)
            ):
                word.text = text

    # ------------------------------------------------------------------ #
    # Ruled-table detection
    # ------------------------------------------------------------------ #
    def _detect_lines(
        self, binary: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return binary masks of horizontal and vertical table lines."""
        h, w = binary.shape[:2]
        h_size = max(10, w // 25)
        v_size = max(10, h // 25)

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
        threshold = 0.5 * h_lines.shape[1]
        ys = [float(y) for y, s in enumerate(row_sums) if s > threshold]
        return _cluster_positions(ys, gap=max(8.0, height * 0.01))

    def _lines_to_col_bands(
        self, v_lines: np.ndarray, width: int
    ) -> list[float]:
        """Convert the vertical-line mask into sorted column separator x-values."""
        col_sums = np.sum(v_lines > 0, axis=0)
        threshold = 0.5 * v_lines.shape[0]
        xs = [float(x) for x, s in enumerate(col_sums) if s > threshold]
        return _cluster_positions(xs, gap=max(8.0, width * 0.01))

    def _grid_is_usable(
        self,
        rows: list[float],
        cols: list[float],
        words: list[OCRWord],
        shape: tuple[int, ...],
    ) -> bool:
        """Decide whether detected rulings form a trustworthy cell grid.

        A ruled grid is only trusted when it has at least two rows and two
        columns spanning most of the page and most detected words fall inside
        its outer bounds. This rejects stray lines and selection marquees.
        """
        if len(rows) < 3 or len(cols) < 3:
            # Need at least 2 cells in each direction (3 separators).
            return False
        h, w = shape[:2]
        if (rows[-1] - rows[0]) < 0.5 * h or (cols[-1] - cols[0]) < 0.5 * w:
            return False
        x0, x1, y0, y1 = cols[0], cols[-1], rows[0], rows[-1]
        inside = 0
        for word in words:
            cx, cy = word.cx, word.cy
            if x0 - 5 <= cx <= x1 + 5 and y0 - 5 <= cy <= y1 + 5:
                inside += 1
        return inside >= 0.7 * len(words)

    def _assign_to_grid(
        self,
        words: list[OCRWord],
        row_bounds: list[float],
        col_bounds: list[float],
    ) -> tuple[list[list[str]], float]:
        """Place each detected word into the ruled grid cell it falls in."""
        n_rows = len(row_bounds) - 1
        n_cols = len(col_bounds) - 1
        table = [["" for _ in range(n_cols)] for _ in range(n_rows)]
        confs: list[float] = []

        def band(value: float, bounds: list[float]) -> int | None:
            for i in range(len(bounds) - 1):
                if bounds[i] <= value < bounds[i + 1]:
                    return i
            return None

        cells: dict[tuple[int, int], list[OCRWord]] = {}
        for word in words:
            r = band(word.cy, row_bounds)
            c = band(word.cx, col_bounds)
            if r is None or c is None:
                continue
            cells.setdefault((r, c), []).append(word)

        for (r, c), cell_words in cells.items():
            cell_words.sort(key=lambda x: x.cx)
            table[r][c] = " ".join(x.text for x in cell_words).strip()
            confs.extend(x.confidence for x in cell_words)

        mean_conf = float(np.mean(confs)) if confs else 0.0
        return table, mean_conf

    # ------------------------------------------------------------------ #
    # Word-geometry reconstruction
    # ------------------------------------------------------------------ #
    def _reconstruct_from_words(
        self, words: list[OCRWord]
    ) -> tuple[list[list[str]], float]:
        """Cluster words into rows and columns using their bounding boxes."""
        heights = [
            _y_extent(w.box)[1] - _y_extent(w.box)[0] for w in words
        ]
        median_h = float(np.median(heights)) or 10.0

        rows = self._group_rows(words, median_h)
        col_bounds = self._column_boundaries(rows, median_h)

        table: list[list[str]] = []
        confs: list[float] = []
        for row in rows:
            cells = ["" for _ in range(len(col_bounds) + 1)]
            for word in sorted(row, key=lambda w: w.cx):
                idx = self._boundary_index(word.cx, col_bounds)
                cells[idx] = (
                    (cells[idx] + " " + word.text).strip()
                    if cells[idx]
                    else word.text
                )
                confs.append(word.confidence)
            table.append(cells)

        self._redistribute_header(table)
        mean_conf = float(np.mean(confs)) if confs else 0.0
        return table, mean_conf

    @staticmethod
    def _group_rows(
        words: list[OCRWord], median_h: float
    ) -> list[list[OCRWord]]:
        """Group words into rows by vertical proximity of their centres."""
        ordered = sorted(words, key=lambda w: w.cy)
        rows: list[list[OCRWord]] = [[ordered[0]]]
        for word in ordered[1:]:
            row_cy = float(np.mean([w.cy for w in rows[-1]]))
            if abs(word.cy - row_cy) <= median_h * 0.6:
                rows[-1].append(word)
            else:
                rows.append([word])
        return rows

    @staticmethod
    def _column_boundaries(
        rows: list[list[OCRWord]], median_h: float
    ) -> list[float]:
        """Derive column separators from whitespace gaps consistent across rows.

        For every row, a gap wider than ~one line height between two adjacent
        words is a candidate separator (its midpoint). Candidates are clustered
        and only kept when supported by several rows, which prevents intra-cell
        spaces (e.g. between "United" and "Kingdom") from splitting a column.
        """
        min_gap = median_h * 0.9
        candidates: list[float] = []
        for row in rows:
            ordered = sorted(row, key=lambda w: _x_extent(w.box)[0])
            for left, right in zip(ordered, ordered[1:], strict=False):
                gap = _x_extent(right.box)[0] - _x_extent(left.box)[1]
                if gap > min_gap:
                    mid = (_x_extent(left.box)[1] + _x_extent(right.box)[0]) / 2
                    candidates.append(mid)
        if not candidates:
            return []
        clustered = _cluster_positions(candidates, gap=median_h * 1.2)
        support_need = max(2, round(0.3 * len(rows)))
        boundaries = [
            b
            for b in clustered
            if sum(1 for c in candidates if abs(c - b) <= median_h * 1.2)
            >= support_need
        ]
        return sorted(boundaries)

    @staticmethod
    def _boundary_index(x: float, boundaries: list[float]) -> int:
        """Return the column index for x given sorted separator positions."""
        idx = 0
        for b in boundaries:
            if x > b:
                idx += 1
            else:
                break
        return idx

    @staticmethod
    def _redistribute_header(table: list[list[str]]) -> None:
        """Nudge merged header tokens over their (empty) data columns.

        Left-aligned headers can land one column left of their right-aligned
        numeric data, merging into the previous cell (e.g. "Units Sold Price").
        When a header cell holds multiple tokens and the next header cell is
        empty but its column carries data, the trailing token is shifted right.
        Mutates ``table`` in place; a no-op for fewer than two rows.
        """
        if len(table) < 2 or not table[0]:
            return
        header = table[0]
        body = table[1:]
        n_cols = len(header)
        for c in range(n_cols - 1):
            tokens = header[c].split()
            if len(tokens) < 2:
                continue
            nxt = c + 1
            col_has_data = any(
                nxt < len(row) and row[nxt].strip() for row in body
            )
            if header[nxt].strip() == "" and col_has_data:
                header[nxt] = tokens[-1]
                header[c] = " ".join(tokens[:-1])

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize(table: list[list[str]]) -> list[list[str]]:
        """Pad all rows to equal width and drop fully-empty rows/columns."""
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
