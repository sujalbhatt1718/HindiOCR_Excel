"""Convert Devanagari (Hindi) numerals to ASCII digits, preserving words.

Only the ten Devanagari digit code points (U+0966–U+096F, ``०१२३४५६७८९``) are
remapped to their ASCII equivalents (``0-9``). Every other character —
including Devanagari letters that spell Hindi words — is left untouched, so
``राम`` stays ``राम`` while ``१२३`` becomes ``123``.

A single :data:`str.translate` table is used instead of regex substitution:
translation is a direct Unicode code-point mapping, which is both faster and
unambiguous.
"""
from __future__ import annotations

from collections.abc import Iterable

# Devanagari digits ० १ २ ३ ४ ५ ६ ७ ८ ९  ->  0 1 2 3 4 5 6 7 8 9
_DEVANAGARI_DIGITS = "०१२३४५६७८९"
_ASCII_DIGITS = "0123456789"

#: Mapping of Devanagari digit code points to ASCII digit code points.
DEVANAGARI_TO_ASCII: dict[int, int] = {
    ord(dev): ord(asc)
    for dev, asc in zip(_DEVANAGARI_DIGITS, _ASCII_DIGITS, strict=True)
}


def convert_numerals(text: str) -> str:
    """Return ``text`` with Devanagari digits replaced by ASCII digits.

    Non-digit characters are preserved verbatim, so mixed content such as
    ``विद्यालय नं. १२`` becomes ``विद्यालय नं. 12`` while pure words are
    unchanged.
    """
    if not text:
        return text
    return text.translate(DEVANAGARI_TO_ASCII)


def convert_row(row: Iterable[str]) -> list[str]:
    """Apply :func:`convert_numerals` to every cell in a row."""
    return [convert_numerals(cell) for cell in row]


def convert_table(table: Iterable[Iterable[str]]) -> list[list[str]]:
    """Apply :func:`convert_numerals` to every cell of a row-major table."""
    return [convert_row(row) for row in table]
