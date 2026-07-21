"""Miscellaneous helper utilities: file validation, sanitization, cleanup."""
from __future__ import annotations

import re
import time
import unicodedata
import uuid
from pathlib import Path

from app.config import settings
from app.utils.exceptions import (
    FileTooLargeError,
    InvalidFileError,
)
from app.utils.logger import logger

# Magic-byte signatures used for lightweight content sniffing.
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_PDF_SIGNATURE = b"%PDF"

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe version of ``filename``.

    Strips directory components, normalises unicode, removes unsafe
    characters and guards against empty / hidden names.
    """
    raw = Path(filename or "").name
    raw = unicodedata.normalize("NFKD", raw)
    ext = Path(raw).suffix.lower()
    stem = raw[: -len(ext)] if ext else raw
    stem = _SAFE_NAME_RE.sub("_", stem).strip("._")
    ext = _SAFE_NAME_RE.sub("", ext)
    if not stem:
        stem = "upload"
    return f"{stem}{ext}"[:120]


def get_extension(filename: str) -> str:
    """Return the lower-cased file extension including the leading dot."""
    return Path(filename or "").suffix.lower()


def detect_kind(content: bytes) -> str | None:
    """Sniff the file kind from magic bytes. Returns 'image', 'pdf' or None."""
    if content.startswith(_PNG_SIGNATURE) or content.startswith(_JPEG_SIGNATURE):
        return "image"
    if content.startswith(_PDF_SIGNATURE):
        return "pdf"
    return None


def validate_upload(filename: str, content: bytes) -> str:
    """Validate an uploaded file's extension, size and magic bytes.

    Returns the detected extension on success and raises an
    :class:`AppError` subclass otherwise.
    """
    ext = get_extension(filename)
    if ext not in settings.allowed_extensions:
        raise InvalidFileError(
            f"Unsupported file type '{ext or 'unknown'}'. "
            f"Allowed: {', '.join(sorted(settings.allowed_extensions))}"
        )

    size = len(content)
    if size == 0:
        raise InvalidFileError("Uploaded file is empty.")
    if size > settings.max_upload_size_bytes:
        raise FileTooLargeError(
            f"File is {size / 1024 / 1024:.1f} MB; the limit is "
            f"{settings.max_upload_size_mb} MB."
        )

    kind = detect_kind(content)
    if kind is None:
        raise InvalidFileError(
            "File content does not match a supported image or PDF format."
        )
    if kind == "pdf" and ext != ".pdf":
        raise InvalidFileError("File content is a PDF but extension is not .pdf")
    if kind == "image" and ext == ".pdf":
        raise InvalidFileError("File content is an image but extension is .pdf")

    return ext


def new_file_id() -> str:
    """Return a new random file identifier."""
    return uuid.uuid4().hex


def save_upload(content: bytes, file_id: str, ext: str) -> Path:
    """Persist uploaded ``content`` to the uploads directory and return path."""
    dest = settings.upload_dir / f"{file_id}{ext}"
    dest.write_bytes(content)
    logger.info("Saved upload {} ({} bytes)", dest.name, len(content))
    return dest


def find_upload(file_id: str) -> Path | None:
    """Locate a previously stored upload by id, regardless of extension."""
    for ext in settings.allowed_extensions:
        candidate = settings.upload_dir / f"{file_id}{ext}"
        if candidate.exists():
            return candidate
    return None


def cleanup_old_files(max_age_minutes: int | None = None) -> int:
    """Delete files in upload/temp dirs older than ``max_age_minutes``.

    Returns the number of files removed.
    """
    max_age = (
        max_age_minutes
        if max_age_minutes is not None
        else settings.file_retention_minutes
    )
    cutoff = time.time() - max_age * 60
    removed = 0
    for directory in (settings.upload_dir, settings.temp_dir):
        for path in Path(directory).glob("*"):
            if path.name == ".gitkeep" or not path.is_file():
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError as exc:  # pragma: no cover - defensive
                logger.warning("Could not remove {}: {}", path, exc)
    if removed:
        logger.info("Cleaned up {} stale file(s)", removed)
    return removed
