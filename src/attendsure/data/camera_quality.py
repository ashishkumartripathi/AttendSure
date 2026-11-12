"""Camera image quality validation for AttendSure.

Provides reusable image quality assessment for classroom camera frames adhering to
Objective 1 (Camera Capture Pipeline) and rural hardware constraints:
- Validates image decoding, format, and dimension thresholds.
- Evaluates luminance (detecting underexposure in dark classrooms or overexposure from glare).
- Evaluates sharpness/blur using Laplacian variance.
- Ensures graceful degradation: poor image quality produces informative warnings
  without blocking manual roll-call persistence.
"""

from dataclasses import dataclass, field
import io
from typing import Optional

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class CameraQualityResult:
    """Represents the outcome of a camera frame quality evaluation."""

    is_valid: bool
    quality_status: str  # "GOOD", "POOR_LIGHTING", "BLURRED", "LOW_RESOLUTION", "INVALID_FORMAT", "EMPTY_FRAME"
    width: int
    height: int
    luminance: float
    blur_score: float
    warnings: list[str] = field(default_factory=list)
    diagnostic_message: str = ""

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "quality_status": self.quality_status,
            "width": self.width,
            "height": self.height,
            "luminance": round(self.luminance, 2),
            "blur_score": round(self.blur_score, 2),
            "warnings": list(self.warnings),
            "diagnostic_message": self.diagnostic_message,
        }


def compute_laplacian_variance(gray_array: np.ndarray) -> float:
    """Compute the variance of the Laplacian filter as a sharpness metric.

    Higher values indicate sharp edges; values below threshold indicate blur.
    Uses OpenCV if available; falls back to discrete 2D convolution via NumPy.

    Args:
        gray_array: 2D NumPy array of grayscale pixel intensities (uint8 or float).

    Returns:
        Non-negative float representing Laplacian variance.
    """
    if gray_array.size == 0 or gray_array.ndim != 2:
        return 0.0

    try:
        import cv2

        return float(cv2.Laplacian(gray_array, cv2.CV_64F).var())
    except Exception:
        # Fallback NumPy discrete 3x3 Laplacian kernel: [[0, 1, 0], [1, -4, 1], [0, 1, 0]]
        img = gray_array.astype(float)
        h, w = img.shape
        if h < 3 or w < 3:
            return 0.0

        center = img[1:-1, 1:-1]
        laplacian = (
            img[:-2, 1:-1]  # top
            + img[2:, 1:-1]  # bottom
            + img[1:-1, :-2]  # left
            + img[1:-1, 2:]  # right
            - 4.0 * center
        )
        return float(np.var(laplacian))


def validate_image_quality(
    image_bytes: Optional[bytes],
    *,
    min_width: int = 320,
    min_height: int = 240,
    min_luminance: float = 40.0,
    max_luminance: float = 220.0,
    min_blur_score: float = 100.0,
) -> CameraQualityResult:
    """Assess whether a captured classroom frame meets minimum quality standards.

    Args:
        image_bytes: Raw bytes from Streamlit camera_input or image upload.
        min_width: Minimum acceptable horizontal resolution in pixels.
        min_height: Minimum acceptable vertical resolution in pixels.
        min_luminance: Grayscale average threshold below which frame is underexposed.
        max_luminance: Grayscale average threshold above which frame is overexposed.
        min_blur_score: Laplacian variance threshold below which frame is blurry.

    Returns:
        CameraQualityResult containing diagnostic scores, warnings, and status.
    """
    if image_bytes is None or len(image_bytes) == 0:
        return CameraQualityResult(
            is_valid=False,
            quality_status="EMPTY_FRAME",
            width=0,
            height=0,
            luminance=0.0,
            blur_score=0.0,
            warnings=["No image data received from the camera."],
            diagnostic_message="Camera feed empty. Please ensure camera permissions are granted.",
        )

    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        width, height = pil_img.size
        format_name = pil_img.format or "UNKNOWN"
    except Exception as exc:
        return CameraQualityResult(
            is_valid=False,
            quality_status="INVALID_FORMAT",
            width=0,
            height=0,
            luminance=0.0,
            blur_score=0.0,
            warnings=[f"Failed to decode image: {exc}"],
            diagnostic_message="Corrupted or unrecognized image format. Please capture a new frame.",
        )

    warnings: list[str] = []
    status = "GOOD"

    # 1. Dimension Check
    if width < min_width or height < min_height:
        warnings.append(
            f"Resolution ({width}×{height}) is below recommended minimum ({min_width}×{min_height})."
        )
        status = "LOW_RESOLUTION"

    # Convert to grayscale array for luminance and edge analysis
    gray_img = pil_img.convert("L")
    gray_array = np.array(gray_img, dtype=np.uint8)

    # 2. Luminance Check (0 to 255)
    mean_luminance = float(np.mean(gray_array))
    if mean_luminance < min_luminance:
        warnings.append(
            f"Classroom frame is underexposed/dark (average luminance: {mean_luminance:.1f} / 255, threshold: {min_luminance})."
        )
        if status == "GOOD":
            status = "POOR_LIGHTING"
    elif mean_luminance > max_luminance:
        warnings.append(
            f"Classroom frame is overexposed/bright (average luminance: {mean_luminance:.1f} / 255, threshold: {max_luminance})."
        )
        if status == "GOOD":
            status = "POOR_LIGHTING"

    # 3. Blur / Sharpness Check
    blur_score = compute_laplacian_variance(gray_array)
    if blur_score < min_blur_score:
        warnings.append(
            f"Image appears blurry or out of focus (sharpness score: {blur_score:.1f}, recommended: ≥{min_blur_score})."
        )
        if status == "GOOD":
            status = "BLURRED"

    # Diagnostic message synthesis
    if status == "GOOD":
        msg = f"Camera frame quality acceptable ({width}×{height}, luminance {mean_luminance:.1f}, sharpness {blur_score:.1f})."
    else:
        msg = (
            f"Quality notice: {'; '.join(warnings)} "
            "Manual headcount confirmation is strongly advised."
        )

    return CameraQualityResult(
        is_valid=(status != "INVALID_FORMAT" and status != "EMPTY_FRAME"),
        quality_status=status,
        width=width,
        height=height,
        luminance=mean_luminance,
        blur_score=blur_score,
        warnings=warnings,
        diagnostic_message=msg,
    )

