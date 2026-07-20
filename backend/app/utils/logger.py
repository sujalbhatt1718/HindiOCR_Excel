"""Loguru-based logging configuration."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import FrameType

from loguru import logger

from app.config import settings

_CONFIGURED = False


class _InterceptHandler(logging.Handler):
    """Route standard-library logging records through Loguru.

    This captures logs emitted by third-party libraries (uvicorn, fastapi,
    paddleocr, ...) so everything ends up in the same sinks.
    """

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame: FrameType | None = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def configure_logging() -> None:
    """Configure Loguru sinks (console + rotating files). Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir: Path = settings.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()

    log_level = "DEBUG" if settings.debug else "INFO"
    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    logger.add(sys.stderr, level=log_level, format=fmt, enqueue=True)
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        level=log_level,
        format=fmt,
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=settings.debug,
    )
    logger.add(
        log_dir / "errors_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format=fmt,
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=settings.debug,
    )

    # Redirect standard logging (uvicorn, etc.) into Loguru.
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        logging_logger = logging.getLogger(name)
        logging_logger.handlers = [_InterceptHandler()]
        logging_logger.propagate = False

    _CONFIGURED = True
    logger.info("Logging configured (level={})", log_level)


__all__ = ["logger", "configure_logging"]
