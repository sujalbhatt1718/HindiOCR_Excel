"""End-to-end OCR pipeline test using real PaddleOCR.

This test downloads PaddleOCR models on first run and is therefore skipped by
default. Enable it explicitly with:

    RUN_OCR_TESTS=1 pytest tests/test_ocr_pipeline.py
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

RUN = os.getenv("RUN_OCR_TESTS") == "1"
pytestmark = pytest.mark.skipif(
    not RUN, reason="Set RUN_OCR_TESTS=1 to run the real OCR pipeline test"
)

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
]


def _font_path() -> str | None:
    for f in _FONT_CANDIDATES:
        if Path(f).exists():
            return f
    return None


def _make_table_image(path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    fp = _font_path()
    assert fp, "A Devanagari font is required for the OCR pipeline test"
    font = ImageFont.truetype(fp, 30)
    img = Image.new("RGB", (760, 220), "white")
    draw = ImageDraw.Draw(img)
    cols = [20, 260, 500, 740]
    rows = [20, 90, 160, 200]
    for x in cols:
        draw.line([(x, rows[0]), (x, rows[-1])], fill="black", width=2)
    for y in rows:
        draw.line([(cols[0], y), (cols[-1], y)], fill="black", width=2)
    cells = [
        ["नाम", "राशि", "City"],
        ["राम कुमार", "1500", "Delhi"],
    ]
    for r, row in enumerate(cells):
        for c, text in enumerate(row):
            draw.text((cols[c] + 10, rows[r] + 20), text, font=font,
                      fill="black")
    img.save(path)


def test_full_pipeline_extracts_table(tmp_path):
    from app.services.document_service import DocumentService

    image_path = tmp_path / "table.png"
    _make_table_image(image_path)

    result = DocumentService().process(image_path, "test-id")
    assert result.n_rows >= 2
    assert result.n_cols >= 2
    flat = " ".join(" ".join(r) for r in result.table)
    # At least some Hindi and English content should be recovered.
    assert any("\u0900" <= ch <= "\u097f" for ch in flat), flat
    assert result.confidence > 0
