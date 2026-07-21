"""Application configuration loaded from environment variables / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ directory (parent of the ``app`` package).
BACKEND_DIR = Path(__file__).resolve().parent.parent
# repository root (parent of ``backend``).
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Central, typed application settings.

    Values are read from environment variables first and fall back to the
    defaults defined here. A local ``.env`` file (see ``.env.example``) is also
    loaded automatically.
    """

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- General ----
    app_name: str = "HindiOCRExcel"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # ---- Storage ----
    upload_dir: Path = BACKEND_DIR / "uploads"
    temp_dir: Path = BACKEND_DIR / "temp"
    log_dir: Path = BACKEND_DIR / "logs"

    # ---- Upload limits ----
    max_upload_size_mb: int = 25
    allowed_extensions: set[str] = Field(
        default={".jpg", ".jpeg", ".png", ".pdf"}
    )

    # ---- OCR ----
    ocr_lang: str = "hi"  # PaddleOCR recognition language (Hindi / Devanagari)
    ocr_use_gpu: bool = False
    ocr_use_angle_cls: bool = True
    ocr_det_db_box_thresh: float = 0.5
    ocr_drop_score: float = 0.30
    # Directory PaddleOCR downloads models to; keeps them out of the home dir.
    ocr_model_dir: Path = BACKEND_DIR / "models"
    # The Devanagari recogniser frequently misreads Latin digits (e.g. "99" as
    # "११"). When enabled, numeric-looking regions are re-recognised with this
    # Latin-optimised model and the result kept when it is confidently numeric.
    ocr_refine_numbers: bool = True
    ocr_digit_lang: str = "en"
    ocr_digit_min_conf: float = 0.60

    # ---- PDF ----
    pdf_render_dpi: int = 200
    max_pdf_pages: int = 30

    # ---- Processing ----
    processing_timeout_sec: int = 600
    file_retention_minutes: int = 120  # temp-file cleanup age

    # ---- CORS ----
    cors_origins: list[str] = Field(default=["*"])

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    def ensure_dirs(self) -> None:
        """Create all runtime directories if they do not yet exist."""
        for directory in (
            self.upload_dir,
            self.temp_dir,
            self.log_dir,
            self.ocr_model_dir,
        ):
            Path(directory).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    settings = Settings()
    settings.ensure_dirs()
    return settings


settings = get_settings()
