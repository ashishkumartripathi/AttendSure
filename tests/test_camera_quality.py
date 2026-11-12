"""Unit tests for camera image quality assessment.

Tests Objective 1 (Camera Capture Pipeline) image quality validation:
- Format decoding and invalid/empty input handling.
- Minimum resolution boundary checks.
- Underexposure (dark frames) and overexposure (glare/whiteout).
- Sharpness and blur detection via Laplacian variance.
- Diagnostic warning construction and non-blocking fallback properties.
"""

import io
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import pytest

from attendsure.data.camera_quality import (
    CameraQualityResult,
    compute_laplacian_variance,
    validate_image_quality,
)


def _make_test_image_bytes(
    width: int = 400,
    height: int = 300,
    color: int = 128,
    draw_shapes: bool = True,
    blur: bool = False,
    fmt: str = "JPEG",
) -> bytes:
    """Helper to generate in-memory synthetic test image bytes."""
    img = Image.new("L", (width, height), color=color)
    if draw_shapes:
        draw = ImageDraw.Draw(img)
        # Draw high-contrast shapes to generate sharp edges
        for x in [50, 150, 250, 320]:
            draw.rectangle([x, 50, x + 40, 220], fill=20)
            draw.ellipse([x + 5, 20, x + 35, 50], fill=40)

    if blur:
        img = img.filter(ImageFilter.GaussianBlur(radius=8.0))

    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_empty_image_bytes_rejected():
    """Verify empty or None image bytes return an EMPTY_FRAME status without crashing."""
    res_none = validate_image_quality(None)
    assert not res_none.is_valid
    assert res_none.quality_status == "EMPTY_FRAME"
    assert len(res_none.warnings) > 0

    res_empty = validate_image_quality(b"")
    assert not res_empty.is_valid
    assert res_empty.quality_status == "EMPTY_FRAME"


def test_corrupted_image_bytes_rejected():
    """Verify unreadable or corrupted binary data returns INVALID_FORMAT."""
    garbage_bytes = b"NOT_A_VALID_JPEG_OR_PNG_HEADER_GARBAGE_12345"
    res = validate_image_quality(garbage_bytes)
    assert not res.is_valid
    assert res.quality_status == "INVALID_FORMAT"
    assert "Failed to decode" in res.warnings[0]


def test_low_resolution_flagged():
    """Verify images below the 320x240 minimum threshold are flagged."""
    low_res_bytes = _make_test_image_bytes(width=200, height=150)
    res = validate_image_quality(low_res_bytes, min_width=320, min_height=240)
    assert res.is_valid  # Still usable for emergency fallback
    assert res.quality_status == "LOW_RESOLUTION"
    assert any("below recommended minimum" in w for w in res.warnings)


def test_underexposed_dark_image_flagged():
    """Verify dark classroom images (luminance < 40) are flagged as POOR_LIGHTING."""
    dark_bytes = _make_test_image_bytes(width=400, height=300, color=20, draw_shapes=False)
    res = validate_image_quality(dark_bytes, min_luminance=40.0)
    assert res.is_valid
    assert res.quality_status == "POOR_LIGHTING"
    assert res.luminance < 40.0
    assert any("underexposed" in w for w in res.warnings)


def test_overexposed_bright_image_flagged():
    """Verify washed-out or overexposed images (luminance > 220) are flagged as POOR_LIGHTING."""
    bright_bytes = _make_test_image_bytes(width=400, height=300, color=245, draw_shapes=False)
    res = validate_image_quality(bright_bytes, max_luminance=220.0)
    assert res.is_valid
    assert res.quality_status == "POOR_LIGHTING"
    assert res.luminance > 220.0
    assert any("overexposed" in w for w in res.warnings)


def test_blurred_image_flagged():
    """Verify blurred images with low Laplacian variance are flagged as BLURRED."""
    blurred_bytes = _make_test_image_bytes(width=400, height=300, color=140, draw_shapes=True, blur=True)
    res = validate_image_quality(blurred_bytes, min_blur_score=100.0)
    assert res.is_valid
    assert res.quality_status == "BLURRED"
    assert res.blur_score < 100.0
    assert any("blurry" in w for w in res.warnings)


def test_clear_sharp_image_acceptable():
    """Verify clear high-contrast images pass with status GOOD."""
    sharp_bytes = _make_test_image_bytes(width=480, height=360, color=140, draw_shapes=True, blur=False)
    res = validate_image_quality(sharp_bytes, min_blur_score=50.0)
    assert res.is_valid
    assert res.quality_status == "GOOD"
    assert len(res.warnings) == 0
    assert "quality acceptable" in res.diagnostic_message


def test_laplacian_variance_numpy_fallback():
    """Verify Laplacian variance calculation handles empty or degenerate arrays gracefully."""
    empty_arr = np.array([])
    assert compute_laplacian_variance(empty_arr) == 0.0

    tiny_arr = np.zeros((2, 2))
    assert compute_laplacian_variance(tiny_arr) == 0.0

    uniform_arr = np.zeros((50, 50), dtype=np.uint8) + 128
    assert compute_laplacian_variance(uniform_arr) == 0.0


def test_to_dict_serialization():
    """Verify CameraQualityResult serializes cleanly to dict format."""
    sharp_bytes = _make_test_image_bytes()
    res = validate_image_quality(sharp_bytes)
    d = res.to_dict()
    assert isinstance(d, dict)
    assert "quality_status" in d
    assert "luminance" in d
    assert "blur_score" in d

