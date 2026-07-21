"""Shared pytest fixtures."""
from __future__ import annotations

import io

import numpy as np
import pytest
from app.main import app
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture(scope="session")
def client() -> TestClient:
    """A FastAPI test client (lifespan runs, OCR warmup is best-effort)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def png_bytes() -> bytes:
    """A tiny valid PNG image as bytes."""
    img = Image.new("RGB", (40, 20), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_table() -> list[list[str]]:
    return [
        ["क्रम", "नाम", "राशि"],
        ["1", "राम कुमार", "1500"],
        ["2", "सीता देवी", "2300"],
    ]


@pytest.fixture
def blank_image() -> np.ndarray:
    return np.full((100, 200, 3), 255, dtype=np.uint8)
