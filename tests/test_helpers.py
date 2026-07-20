"""Tests for validation / sanitization helpers."""
from __future__ import annotations

import pytest
from app.utils.exceptions import FileTooLargeError, InvalidFileError
from app.utils.helpers import (
    detect_kind,
    get_extension,
    sanitize_filename,
    validate_upload,
)


def test_sanitize_filename_strips_paths_and_unsafe_chars():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("my file (1).png") == "my_file_1.png"
    assert sanitize_filename("") == "upload"
    assert sanitize_filename("रिपोर्ट.png").endswith(".png")


def test_get_extension():
    assert get_extension("a.PNG") == ".png"
    assert get_extension("a.tar.gz") == ".gz"
    assert get_extension("noext") == ""


def test_detect_kind(png_bytes):
    assert detect_kind(png_bytes) == "image"
    assert detect_kind(b"%PDF-1.7\n...") == "pdf"
    assert detect_kind(b"not a real file") is None


def test_validate_upload_accepts_png(png_bytes):
    assert validate_upload("image.png", png_bytes) == ".png"


def test_validate_upload_rejects_bad_extension(png_bytes):
    with pytest.raises(InvalidFileError):
        validate_upload("image.gif", png_bytes)


def test_validate_upload_rejects_mismatched_content(png_bytes):
    with pytest.raises(InvalidFileError):
        validate_upload("image.pdf", png_bytes)


def test_validate_upload_rejects_empty():
    with pytest.raises(InvalidFileError):
        validate_upload("image.png", b"")


def test_validate_upload_rejects_too_large(png_bytes):
    from app.config import settings

    big = png_bytes + b"\x00" * (settings.max_upload_size_bytes + 1)
    with pytest.raises(FileTooLargeError):
        validate_upload("image.png", big)
