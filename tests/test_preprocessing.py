"""Tests for the OpenCV preprocessing pipeline."""
from __future__ import annotations

import numpy as np
from app.services.preprocessing_service import (
    PreprocessingService,
    apply_clahe,
    deskew,
    resize,
    to_grayscale,
)


def test_to_grayscale_shapes():
    color = np.zeros((10, 10, 3), dtype=np.uint8)
    gray = to_grayscale(color)
    assert gray.ndim == 2
    # Already-gray passthrough
    assert to_grayscale(gray).ndim == 2


def test_resize_upscales_small_images():
    small = np.zeros((50, 50, 3), dtype=np.uint8)
    out = resize(small)
    assert max(out.shape[:2]) >= 1000


def test_clahe_returns_same_shape():
    gray = (np.random.rand(64, 64) * 255).astype(np.uint8)
    assert apply_clahe(gray).shape == gray.shape


def test_deskew_handles_blank():
    gray = np.full((80, 80), 255, dtype=np.uint8)
    assert deskew(gray).shape == gray.shape


def test_full_pipeline_returns_binary(blank_image):
    out = PreprocessingService().full_pipeline(blank_image)
    assert out.ndim == 2
    assert out.dtype == np.uint8


def test_prepare_for_detection_returns_bgr(blank_image):
    out = PreprocessingService().prepare_for_detection(blank_image)
    assert out.ndim == 3
