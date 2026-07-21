"""Tests for table reconstruction logic (clustering + normalization)."""
from __future__ import annotations

import numpy as np
from app.services.ocr_service import OCRWord
from app.services.table_service import (
    TableService,
    _cluster_positions,
    _is_ascii_numeric,
)


def _word(text, x, y, w=40, h=20):
    """Build an OCRWord with an axis-aligned box at (x, y)."""
    box = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
    return OCRWord(text=text, confidence=0.9, box=box)


def test_cluster_positions_merges_close_values():
    assert _cluster_positions([10, 11, 12, 100, 101], gap=5) == [11.0, 100.5]
    assert _cluster_positions([], gap=5) == []


def test_reconstruct_from_words_builds_grid():
    svc = TableService.__new__(TableService)  # no OCR needed for this method
    words = [
        _word("Name", 10, 10), _word("Age", 200, 10),
        _word("Ram", 10, 60), _word("30", 200, 60),
        _word("Sita", 10, 110), _word("25", 200, 110),
    ]
    table, conf = svc._reconstruct_from_words(words)
    assert conf > 0
    assert len(table) == 3
    assert table[0] == ["Name", "Age"]
    assert table[1] == ["Ram", "30"]
    assert table[2] == ["Sita", "25"]


def test_reconstruct_keeps_multiword_cell_together():
    """A gap within a cell (e.g. "United Kingdom") must not split a column."""
    svc = TableService.__new__(TableService)
    words = [
        _word("Country", 10, 10, w=90), _word("Sales", 400, 10, w=70),
        _word("United", 10, 60, w=70), _word("Kingdom", 90, 60, w=90),
        _word("9528", 430, 60, w=50),
        _word("France", 10, 110, w=80), _word("4100", 430, 110, w=50),
    ]
    table, _ = svc._reconstruct_from_words(words)
    assert table[1][0] == "United Kingdom"
    assert table[1][1] == "9528"
    assert table[2] == ["France", "4100"]


def test_redistribute_header_moves_merged_token():
    table = [
        ["Country", "Units Sold Price", "", "Revenue"],
        ["France", "4100", "36", "147600"],
        ["Total", "40190", "", "2164672"],
    ]
    TableService._redistribute_header(table)
    assert table[0] == ["Country", "Units Sold", "Price", "Revenue"]


def test_normalize_pads_and_trims():
    table = [
        ["", "", ""],
        ["a", "b"],
        ["c", "d", "e"],
        ["", "", ""],
    ]
    out = TableService._normalize(table)
    # Leading/trailing empty rows removed, rows padded to equal width.
    assert out == [["a", "b", ""], ["c", "d", "e"]]


def test_normalize_drops_empty_columns():
    table = [["a", "", "b"], ["c", "", "d"]]
    assert TableService._normalize(table) == [["a", "b"], ["c", "d"]]


def test_is_ascii_numeric():
    assert _is_ascii_numeric("99")
    assert _is_ascii_numeric("2,164,672")
    assert _is_ascii_numeric("10/02/2026")
    assert not _is_ascii_numeric("११")      # Devanagari digits
    assert not _is_ascii_numeric("o0hb")    # noisy letters
    assert not _is_ascii_numeric("राम")     # Hindi word
    assert not _is_ascii_numeric("")


class _StubOCR:
    """Minimal OCR stub returning a fixed region result."""

    def __init__(self, text, conf):
        self._text = text
        self._conf = conf
        self.calls = 0

    def recognize_region(self, image, lang=None):
        self.calls += 1
        return self._text, self._conf


def test_refine_numbers_upgrades_latin_digits():
    """A Devanagari misread of Latin digits is replaced by the English read."""
    svc = TableService.__new__(TableService)
    svc.ocr = _StubOCR("99", 0.99)
    img = np.zeros((50, 200, 3), dtype=np.uint8)
    word = _word("११", 10, 10)  # hi model misread of "99"
    svc._refine_numbers(img, [word])
    assert word.text == "99"


def test_refine_numbers_keeps_genuine_devanagari():
    """A real Devanagari numeral is kept when English cannot read it cleanly."""
    svc = TableService.__new__(TableService)
    svc.ocr = _StubOCR("o0hb", 0.9)  # English garbage on a Hindi crop
    img = np.zeros((50, 200, 3), dtype=np.uint8)
    word = _word("१५००", 10, 10)
    svc._refine_numbers(img, [word])
    assert word.text == "१५००"


def test_refine_numbers_skips_hindi_words():
    svc = TableService.__new__(TableService)
    svc.ocr = _StubOCR("should-not-be-used", 1.0)
    img = np.zeros((50, 200, 3), dtype=np.uint8)
    word = _word("राम", 10, 10)
    svc._refine_numbers(img, [word])
    assert word.text == "राम"
    assert svc.ocr.calls == 0
