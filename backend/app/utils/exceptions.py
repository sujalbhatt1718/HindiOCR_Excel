"""Domain-specific exceptions and their HTTP mappings."""
from __future__ import annotations

from fastapi import status


class AppError(Exception):
    """Base class for all application errors.

    Attributes:
        message: Human-readable error message returned to the client.
        status_code: HTTP status code to respond with.
        error_code: Stable, machine-readable error identifier.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.__class__.__doc__ or "Application error"
        super().__init__(self.message)


class InvalidFileError(AppError):
    """The uploaded file is invalid or unsupported."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "invalid_file"


class FileTooLargeError(AppError):
    """The uploaded file exceeds the maximum allowed size."""

    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    error_code = "file_too_large"


class CorruptedFileError(AppError):
    """The uploaded file is corrupted and cannot be read."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "corrupted_file"


class FileNotFoundAppError(AppError):
    """The requested file id does not exist."""

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "file_not_found"


class NoTableFoundError(AppError):
    """No table could be detected in the document."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "no_table_found"


class OCRProcessingError(AppError):
    """OCR processing failed."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "ocr_failure"


class OCRModelLoadError(AppError):
    """The OCR models could not be downloaded or loaded."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "ocr_model_load_failed"


class PDFProcessingError(AppError):
    """The PDF could not be processed."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "pdf_processing_failed"


class ExcelExportError(AppError):
    """Excel generation failed."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "excel_export_failed"


class ProcessingTimeoutError(AppError):
    """Processing exceeded the configured timeout."""

    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = "processing_timeout"
