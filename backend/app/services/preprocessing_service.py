"""Image preprocessing pipeline built on OpenCV.

The pipeline is designed to improve OCR accuracy on scanned documents, mobile
camera captures and printed forms. Each step is implemented as a small, pure
function so the pipeline is easy to test and reason about.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.utils.logger import logger

# Maximum dimension (px) an image is scaled to before OCR. Large mobile photos
# are downscaled for speed; small scans are upscaled for legibility.
_TARGET_MAX_DIM = 2000
_TARGET_MIN_DIM = 1000


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert a BGR/BGRA image to single-channel grayscale."""
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def resize(image: np.ndarray) -> np.ndarray:
    """Scale image so its largest side lies within a sensible OCR range."""
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest == 0:
        return image
    scale = 1.0
    if longest > _TARGET_MAX_DIM:
        scale = _TARGET_MAX_DIM / longest
    elif longest < _TARGET_MIN_DIM:
        scale = _TARGET_MIN_DIM / longest
    if abs(scale - 1.0) < 1e-3:
        return image
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=interp)


def remove_noise(gray: np.ndarray) -> np.ndarray:
    """Edge-preserving denoise using non-local means."""
    return cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7,
                                    searchWindowSize=21)


def gaussian_blur(gray: np.ndarray) -> np.ndarray:
    """Light Gaussian blur to suppress high-frequency speckle."""
    return cv2.GaussianBlur(gray, (3, 3), 0)


def median_blur(gray: np.ndarray) -> np.ndarray:
    """Median blur; effective against salt-and-pepper noise."""
    return cv2.medianBlur(gray, 3)


def apply_clahe(gray: np.ndarray) -> np.ndarray:
    """Contrast Limited Adaptive Histogram Equalization."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def remove_shadow(gray: np.ndarray) -> np.ndarray:
    """Normalise uneven illumination / shadows via background division."""
    dilated = cv2.dilate(gray, np.ones((7, 7), np.uint8))
    background = cv2.medianBlur(dilated, 21)
    diff = 255 - cv2.absdiff(gray, background)
    return cv2.normalize(  # type: ignore[call-overload]
        diff, None, 0, 255, cv2.NORM_MINMAX
    )


def adaptive_threshold(gray: np.ndarray) -> np.ndarray:
    """Binarize using an adaptive Gaussian threshold."""
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 15,
    )


def morphological_open(binary: np.ndarray) -> np.ndarray:
    """Opening removes isolated foreground noise pixels."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)


def morphological_close(binary: np.ndarray) -> np.ndarray:
    """Closing fills small holes inside glyph strokes."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)


def sharpen(gray: np.ndarray) -> np.ndarray:
    """Unsharp-mask style sharpening."""
    blurred = cv2.GaussianBlur(gray, (0, 0), 3)
    return cv2.addWeighted(gray, 1.5, blurred, -0.5, 0)


def remove_border(gray: np.ndarray) -> np.ndarray:
    """Crop scanner borders by locating the largest content contour."""
    _, thresh = cv2.threshold(gray, 0, 255,
                              cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return gray
    largest = max(contours, key=cv2.contourArea)
    area_ratio = cv2.contourArea(largest) / (gray.shape[0] * gray.shape[1])
    # Only crop if the content region is large and clearly bordered.
    if area_ratio < 0.4 or area_ratio > 0.99:
        return gray
    x, y, w, h = cv2.boundingRect(largest)
    pad = 5
    y0, y1 = max(0, y - pad), min(gray.shape[0], y + h + pad)
    x0, x1 = max(0, x - pad), min(gray.shape[1], x + w + pad)
    return gray[y0:y1, x0:x1]


def deskew(gray: np.ndarray) -> np.ndarray:
    """Estimate and correct small skew angles using minimum-area rectangle."""
    inverted = cv2.bitwise_not(gray)
    _, thresh = cv2.threshold(inverted, 0, 255,
                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 50:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5 or abs(angle) > 20:
        # Ignore negligible or implausibly large angles.
        return gray
    (h, w) = gray.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        gray, matrix, (w, h),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
    )


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def perspective_correct(image: np.ndarray) -> np.ndarray:
    """Detect a document quadrilateral and warp it to a top-down view."""
    gray = to_grayscale(image)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blur, 50, 150)
    edged = cv2.dilate(edged, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edged, cv2.RETR_LIST,
                                   cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    img_area = image.shape[0] * image.shape[1]
    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4 and cv2.contourArea(approx) > 0.5 * img_area:
            rect = _order_points(approx.reshape(4, 2).astype("float32"))
            (tl, tr, br, bl) = rect
            width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
            height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
            if width < 50 or height < 50:
                return image
            dst = np.array(
                [[0, 0], [width - 1, 0], [width - 1, height - 1],
                 [0, height - 1]],
                dtype="float32",
            )
            matrix = cv2.getPerspectiveTransform(rect, dst)
            return cv2.warpPerspective(image, matrix, (width, height))
    return image


class PreprocessingService:
    """High-level orchestrator that composes the preprocessing steps."""

    def prepare_for_detection(self, image: np.ndarray) -> np.ndarray:
        """Return a cleaned BGR image suitable for table-line detection.

        Perspective correction, resizing and deskew are applied but the image
        is kept in colour so PaddleOCR can run on the original glyphs.
        """
        corrected = perspective_correct(image)
        corrected = resize(corrected)
        gray = to_grayscale(corrected)
        gray = deskew(gray)
        # Return colour version aligned to the deskewed grayscale dimensions.
        if corrected.ndim == 3 and corrected.shape[:2] != gray.shape[:2]:
            corrected = cv2.resize(corrected, (gray.shape[1], gray.shape[0]))
        return corrected if corrected.ndim == 3 else cv2.cvtColor(
            gray, cv2.COLOR_GRAY2BGR
        )

    def binarize_for_lines(self, image: np.ndarray) -> np.ndarray:
        """Produce a clean binary image used for morphological line detection."""
        gray = to_grayscale(image)
        gray = remove_shadow(gray)
        gray = apply_clahe(gray)
        gray = median_blur(gray)
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY_INV, 15, 10,
        )
        return binary

    def enhance_cell(self, cell: np.ndarray) -> np.ndarray:
        """Enhance a small cropped cell image before per-cell OCR."""
        if cell.size == 0:
            return cell
        gray = to_grayscale(cell)
        gray = apply_clahe(gray)
        gray = sharpen(gray)
        # Upscale tiny cells so PaddleOCR sees enough pixels per glyph.
        h, w = gray.shape[:2]
        if max(h, w) < 60 and max(h, w) > 0:
            scale = 60 / max(h, w)
            gray = cv2.resize(gray, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_CUBIC)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    def full_pipeline(self, image: np.ndarray) -> np.ndarray:
        """Run the complete documented pipeline, returning a binary image.

        Used for the fallback OCR path (no table lines) and for visual
        diagnostics. Steps mirror the project specification.
        """
        try:
            work = perspective_correct(image)
            work = resize(work)
            gray = to_grayscale(work)
            gray = remove_shadow(gray)
            gray = remove_noise(gray)
            gray = gaussian_blur(gray)
            gray = median_blur(gray)
            gray = apply_clahe(gray)
            gray = sharpen(gray)
            gray = remove_border(gray)
            gray = deskew(gray)
            binary = adaptive_threshold(gray)
            binary = morphological_open(binary)
            binary = morphological_close(binary)
            return binary
        except cv2.error as exc:  # pragma: no cover - defensive
            logger.warning("Preprocessing failed, using grayscale: {}", exc)
            return to_grayscale(image)
