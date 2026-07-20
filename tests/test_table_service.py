"""Tests for table reconstruction logic (clustering + normalization)."""
from __future__ import annotations

from app.services.ocr_service import OCRWord
from app.services.table_service import TableService, _cluster_positions


def _word(text, x, y, w=40, h=20):
    """Build an OCRWord with an axis-aligned box at (x, y)."""
    box = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
    return OCRWord(text=text, confidence=0.9, box=box)


def test_cluster_positions_merges_close_values():
    assert _cluster_positions([10, 11, 12, 100, 101], gap=5) == [11.0, 100.5]
    assert _cluster_positions([], gap=5) == []


def test_cluster_words_reconstructs_grid():
    svc = TableService.__new__(TableService)  # no OCR needed for this method
    words = [
        _word("Name", 10, 10), _word("Age", 200, 10),
        _word("Ram", 10, 60), _word("30", 200, 60),
        _word("Sita", 10, 110), _word("25", 200, 110),
    ]
    table, conf = svc._cluster_words(words)
    assert conf > 0
    assert len(table) == 3
    assert table[0] == ["Name", "Age"]
    assert table[1] == ["Ram", "30"]
    assert table[2] == ["Sita", "25"]


def test_cluster_words_empty():
    svc = TableService.__new__(TableService)
    assert svc._cluster_words([]) == ([], 0.0)


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
