"""Tests for Devanagari→ASCII numeral conversion."""
from __future__ import annotations

import pytest
from app.utils.numeral_converter import (
    convert_numerals,
    convert_row,
    convert_table,
)


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("१२३", "123"),
        ("२०२५", "2025"),
        ("५४६७८", "54678"),
        ("८९.५०", "89.50"),
        ("₹१२५०", "₹1250"),
        ("१०/०२/२०२६", "10/02/2026"),
        ("विद्यालय नं. १२", "विद्यालय नं. 12"),
        ("0123456789", "0123456789"),  # ASCII unchanged
    ],
)
def test_convert_numerals_examples(src: str, expected: str) -> None:
    assert convert_numerals(src) == expected


@pytest.mark.parametrize("word", ["राम", "सीता देवी", "John Doe", "क्रम"])
def test_hindi_and_english_words_unchanged(word: str) -> None:
    assert convert_numerals(word) == word


def test_all_ten_digits_map() -> None:
    assert convert_numerals("०१२३४५६७८९") == "0123456789"


def test_empty_and_none_like() -> None:
    assert convert_numerals("") == ""


def test_convert_row() -> None:
    assert convert_row(["राम", "१५००", "Delhi"]) == ["राम", "1500", "Delhi"]


def test_convert_table_preserves_shape_and_words() -> None:
    table = [["क्रम", "नाम", "राशि"], ["१", "राम", "१५००"], ["२", "John", "२३०"]]
    assert convert_table(table) == [
        ["क्रम", "नाम", "राशि"],
        ["1", "राम", "1500"],
        ["2", "John", "230"],
    ]
