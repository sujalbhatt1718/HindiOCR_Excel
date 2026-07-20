"""PaddleOCR wrapper: lazy model loading, GPU detection, cell + page OCR."""
from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np

from app.config import settings
from app.utils.exceptions import OCRModelLoadError, OCRProcessingError
from app.utils.logger import logger


@dataclass
class OCRWord:
    """A single detected text region."""

    text: str
    confidence: float
    box: list[list[float]]  # 4 corner points [[x,y], ...]

    @property
    def cx(self) -> float:
        xs = [p[0] for p in self.box]
        return sum(xs) / len(xs)

    @property
    def cy(self) -> float:
        ys = [p[1] for p in self.box]
        return sum(ys) / len(ys)


def gpu_available() -> bool:
    """Return True if a CUDA-capable GPU is usable by paddle."""
    try:
        import paddle

        return bool(paddle.device.is_compiled_with_cuda()) and (
            paddle.device.cuda.device_count() > 0
        )
    except Exception:  # pragma: no cover - depends on runtime
        return False


class OCRService:
    """Thread-safe, lazily-initialised PaddleOCR engine manager.

    A separate PaddleOCR instance is cached per language. Models are
    downloaded automatically by PaddleOCR on first use; if a GPU is not
    available the engine transparently falls back to CPU.
    """

    def __init__(self) -> None:
        self._engines: dict[str, object] = {}
        self._lock = threading.Lock()
        self._use_gpu = settings.ocr_use_gpu and gpu_available()
        if settings.ocr_use_gpu and not self._use_gpu:
            logger.warning("GPU requested but unavailable; falling back to CPU")

    @property
    def use_gpu(self) -> bool:
        return self._use_gpu

    @property
    def is_loaded(self) -> bool:
        return bool(self._engines)

    def _build_engine(self, lang: str):
        from paddleocr import PaddleOCR

        logger.info("Loading PaddleOCR engine (lang={}, gpu={})", lang,
                    self._use_gpu)
        try:
            return PaddleOCR(
                use_angle_cls=settings.ocr_use_angle_cls,
                lang=lang,
                use_gpu=self._use_gpu,
                show_log=False,
                det_db_box_thresh=settings.ocr_det_db_box_thresh,
                drop_score=settings.ocr_drop_score,
            )
        except Exception as exc:  # model download / init failure
            logger.exception("Failed to initialise PaddleOCR")
            raise OCRModelLoadError(
                f"Could not load OCR models for lang '{lang}': {exc}"
            ) from exc

    def get_engine(self, lang: str | None = None):
        """Return (and cache) the PaddleOCR engine for ``lang``."""
        lang = lang or settings.ocr_lang
        engine = self._engines.get(lang)
        if engine is not None:
            return engine
        with self._lock:
            engine = self._engines.get(lang)
            if engine is None:
                engine = self._build_engine(lang)
                self._engines[lang] = engine
            return engine

    def warmup(self, lang: str | None = None) -> None:
        """Eagerly load models (used at startup) so first request is fast."""
        try:
            self.get_engine(lang)
        except OCRModelLoadError:
            # Non-fatal at startup; the error resurfaces on first real request.
            logger.warning("OCR warmup failed; will retry on first request")

    def ocr_page(
        self, image: np.ndarray, lang: str | None = None
    ) -> list[OCRWord]:
        """Run full detection + recognition on a page image."""
        engine = self.get_engine(lang)
        try:
            raw = engine.ocr(image, cls=settings.ocr_use_angle_cls)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.exception("Page OCR failed")
            raise OCRProcessingError(f"OCR failed: {exc}") from exc

        words: list[OCRWord] = []
        if not raw or raw[0] is None:
            return words
        for line in raw[0]:
            box, (text, conf) = line
            text = (text or "").strip()
            if text:
                words.append(
                    OCRWord(text=text, confidence=float(conf), box=box)
                )
        return words

    def ocr_cell(
        self, cell_image: np.ndarray, lang: str | None = None
    ) -> tuple[str, float]:
        """Recognition-only OCR on a pre-cropped cell image.

        Returns the concatenated text and mean confidence. Detection is still
        used so multi-line cells are handled, but results are merged.
        """
        if cell_image is None or cell_image.size == 0:
            return "", 0.0
        engine = self.get_engine(lang)
        try:
            raw = engine.ocr(cell_image, cls=settings.ocr_use_angle_cls)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Cell OCR failed: {}", exc)
            return "", 0.0

        if not raw or raw[0] is None:
            return "", 0.0
        parts: list[str] = []
        confs: list[float] = []
        for line in raw[0]:
            _, (text, conf) = line
            text = (text or "").strip()
            if text:
                parts.append(text)
                confs.append(float(conf))
        if not parts:
            return "", 0.0
        return " ".join(parts), sum(confs) / len(confs)


# Module-level singleton reused across requests.
ocr_service = OCRService()
