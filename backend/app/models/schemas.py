"""Pydantic request/response models."""
from __future__ import annotations

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """Response returned after a successful upload."""

    file_id: str = Field(..., description="Identifier used for later processing")
    filename: str = Field(..., description="Sanitized stored filename")
    kind: str = Field(..., description="'image' or 'pdf'")
    size_bytes: int = Field(..., description="Stored file size in bytes")
    pages: int = Field(1, description="Number of pages (PDF) or 1 for images")


class ProcessRequest(BaseModel):
    """Request body for the /process endpoint."""

    file_id: str = Field(..., description="File id returned by /upload")
    lang: str | None = Field(
        None, description="Override OCR language (default from config)"
    )


class PageResult(BaseModel):
    """Extracted table for a single page/image."""

    page: int = Field(..., description="1-based page number")
    rows: list[list[str]] = Field(
        default_factory=list, description="Table cell values, row-major"
    )
    n_rows: int = 0
    n_cols: int = 0
    confidence: float = Field(
        0.0, description="Mean OCR confidence for the page (0-1)"
    )


class ProcessResponse(BaseModel):
    """Response returned after OCR + table reconstruction."""

    file_id: str
    pages: list[PageResult] = Field(default_factory=list)
    table: list[list[str]] = Field(
        default_factory=list,
        description="Merged table across all pages (row-major)",
    )
    n_rows: int = 0
    n_cols: int = 0
    confidence: float = Field(0.0, description="Overall mean confidence (0-1)")
    processing_time: float = Field(..., description="Seconds spent processing")


class ExportRequest(BaseModel):
    """Request body for the /export endpoint."""

    table: list[list[str]] = Field(
        ..., description="Edited table data, row-major (first row = header)"
    )
    filename: str = Field(
        "hindi_ocr_export", description="Base filename (without extension)"
    )
    sheet_name: str = Field("Sheet1", description="Worksheet name")
    header: bool = Field(True, description="Treat first row as a bold header")


class HealthResponse(BaseModel):
    """Response for the /health endpoint."""

    status: str
    version: str
    ocr_loaded: bool
    gpu_available: bool


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    error: str = Field(..., description="Machine-readable error code")
    detail: str = Field(..., description="Human-readable message")
