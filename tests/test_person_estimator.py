"""Unit tests and evaluation benchmark for classroom person-count estimation.

Tests Objective 1 (Camera Capture Pipeline) person estimation:
- Estimator behavior on clean synthetic student silhouettes.
- Anatomical aspect ratio and bounding area filtering.
- Bench cluster area normalization when students sit closely.
- Transparent uncertainty handling under poor lighting or heavy blur.
- Labelled evaluation dataset reporting actual MAE (Mean Absolute Error).
"""

import io
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import pytest

from attendsure.data.camera_quality import validate_image_quality
from attendsure.data.person_estimator import (
    PersonEstimateResult,
    estimate_classroom_occupancy,
)


def _generate_synthetic_classroom_frame(
    student_positions: list[int],
    width: int = 500,
    height: int = 350,
    blur: bool = False,
    dark: bool = False,
) -> bytes:
    """Render a synthetic classroom frame with known student silhouette positions."""
    bg_color = 20 if dark else 180
    img = Image.new("L", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    for x in student_positions:
        # Upper torso / body (H/W aspect ratio ~ 2.0)
        draw.rectangle([x - 20, 140, x + 20, 260], fill=40 if not dark else 200)
        # Head
        draw.ellipse([x - 12, 100, x + 12, 140], fill=50 if not dark else 210)

    if blur:
        img = img.filter(ImageFilter.GaussianBlur(radius=7.0))

    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_estimator_on_empty_or_invalid_image():
    """Verify estimator returns None count and flags uncertain on unreadable input."""
    res_none = estimate_classroom_occupancy(None)
    assert res_none.estimated_count is None
    assert res_none.is_uncertain
    assert "empty, corrupted, or unreadable" in res_none.explanation

    res_garbage = estimate_classroom_occupancy(b"invalid_bytes_xyz")
    assert res_none.estimated_count is None
    assert res_garbage.is_uncertain


def test_estimator_detects_isolated_student_silhouettes():
    """Verify estimator identifies 3 distinct seated student silhouettes."""
    test_bytes = _generate_synthetic_classroom_frame(student_positions=[80, 220, 380])
    res = estimate_classroom_occupancy(test_bytes)

    assert res.estimated_count is not None
    assert res.estimated_count == 3
    assert not res.is_uncertain
    assert res.confidence_score is not None and res.confidence_score >= 0.70
    assert "3 student(s) detected" in res.explanation


def test_estimator_flags_uncertainty_on_blurred_image():
    """Verify estimator flags is_uncertain=True when blur prevents sharp boundaries."""
    blurred_bytes = _generate_synthetic_classroom_frame(student_positions=[100, 250, 400], blur=True)
    res = estimate_classroom_occupancy(blurred_bytes)

    assert res.is_uncertain
    assert res.confidence_score is not None and res.confidence_score < 0.65
    assert "uncertainty" in res.explanation.lower()


def test_estimator_filters_out_non_human_shapes():
    """Verify wide horizontal bars (e.g. wall panels) or tiny noise are filtered out."""
    img = Image.new("L", (500, 350), color=180)
    draw = ImageDraw.Draw(img)

    # 1 genuine student
    draw.rectangle([100, 140, 140, 260], fill=40)
    draw.ellipse([110, 100, 130, 140], fill=50)

    # Tiny noise speckles (< 0.5% area)
    draw.point([20, 20], fill=0)
    draw.rectangle([30, 30, 34, 34], fill=0)

    # Very wide horizontal line (desk edge, aspect ratio < 0.1)
    draw.rectangle([50, 320, 450, 325], fill=0)

    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    res = estimate_classroom_occupancy(buf.getvalue())
    assert res.estimated_count == 1


def test_bench_cluster_area_normalization():
    """Verify that a merged double-student bench blob is normalized to approximately 2 students."""
    img = Image.new("L", (500, 350), color=180)
    draw = ImageDraw.Draw(img)

    # 1 reference isolated student
    draw.rectangle([80, 140, 120, 260], fill=40)
    draw.ellipse([90, 100, 110, 140], fill=50)

    # 1 double-width cluster representing 2 adjacent students sharing a bench
    draw.rectangle([250, 140, 350, 260], fill=40)
    draw.ellipse([265, 100, 285, 140], fill=50)
    draw.ellipse([315, 100, 335, 140], fill=50)

    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    res = estimate_classroom_occupancy(buf.getvalue())
    # Should estimate 1 (isolated) + ~2 (from cluster) = ~3 students
    assert res.estimated_count in (2, 3, 4)


def test_labelled_evaluation_benchmark_and_mae():
    """Run evaluation over a labelled test suite and report actual Mean Absolute Error (MAE).

    Acceptance check for Objective 1: Reports empirical counting error against labelled benchmarks.
    """
    ground_truth_samples = [
        # (student_positions, ground_truth_count)
        ([100], 1),
        ([100, 250], 2),
        ([80, 220, 360], 3),
        ([60, 160, 270, 380], 4),
        ([50, 130, 220, 310, 410], 5),
    ]

    errors: list[int] = []
    overcounts = 0
    undercounts = 0

    for positions, true_count in ground_truth_samples:
        frame_bytes = _generate_synthetic_classroom_frame(student_positions=positions)
        res = estimate_classroom_occupancy(frame_bytes)
        pred = res.estimated_count if res.estimated_count is not None else 0

        err = abs(pred - true_count)
        errors.append(err)
        if pred > true_count:
            overcounts += 1
        elif pred < true_count:
            undercounts += 1

    mae = float(np.mean(errors))
    max_err = max(errors)

    # Verify MAE on standard isolated seated scenes is low (well within proposed target MAE <= 3)
    assert mae <= 1.0, f"Benchmark MAE ({mae:.2f}) exceeded acceptable benchmark bound."
    assert max_err <= 1, f"Max error ({max_err}) exceeded acceptable single-sample bound."


def test_six_camera_benchmark_cases():
    """Verify camera estimation and quality behavior across the 6 required benchmark cases."""
    # 1. Clear Image
    clear_bytes = _generate_synthetic_classroom_frame(student_positions=[120, 250, 380])
    q_clear = validate_image_quality(clear_bytes)
    res_clear = estimate_classroom_occupancy(clear_bytes, quality_result=q_clear, expected_enrollment=30)
    assert q_clear.quality_status == "GOOD"
    assert q_clear.is_valid is True
    assert res_clear.estimated_count == 3
    assert res_clear.confidence_score >= 0.70
    assert res_clear.is_uncertain is False

    # 2. Blurry Image
    blur_bytes = _generate_synthetic_classroom_frame(student_positions=[120, 250, 380], blur=True)
    q_blur = validate_image_quality(blur_bytes)
    res_blur = estimate_classroom_occupancy(blur_bytes, quality_result=q_blur, expected_enrollment=30)
    assert q_blur.quality_status == "BLURRED"
    assert res_blur.is_uncertain is True
    assert "sharpness" in res_blur.uncertainty_reason

    # 3. Dark/Underexposed Image
    dark_bytes = _generate_synthetic_classroom_frame(student_positions=[120, 250, 380], dark=True)
    q_dark = validate_image_quality(dark_bytes)
    res_dark = estimate_classroom_occupancy(dark_bytes, quality_result=q_dark, expected_enrollment=30)
    assert q_dark.quality_status == "POOR_LIGHTING"
    assert res_dark.is_uncertain is True

    # 4. Invalid File
    corrupt_bytes = b"invalid_binary_corrupted_payload"
    q_invalid = validate_image_quality(corrupt_bytes)
    res_invalid = estimate_classroom_occupancy(corrupt_bytes, quality_result=q_invalid, expected_enrollment=30)
    assert q_invalid.quality_status == "INVALID_FORMAT"
    assert q_invalid.is_valid is False
    assert res_invalid.estimated_count is None
    assert res_invalid.is_uncertain is True

    # 5. Blank / No Silhouettes
    blank_img = Image.new("L", (500, 350), color=180)
    buf = io.BytesIO()
    blank_img.save(buf, format="JPEG")
    blank_bytes = buf.getvalue()
    q_blank = validate_image_quality(blank_bytes)
    res_blank = estimate_classroom_occupancy(blank_bytes, quality_result=q_blank, expected_enrollment=30)
    assert res_blank.estimated_count == 0
    assert res_blank.is_uncertain is True

    # 6. Multiple Silhouettes
    multi_bytes = _generate_synthetic_classroom_frame(student_positions=[60, 140, 220, 300, 380, 440])
    q_multi = validate_image_quality(multi_bytes)
    res_multi = estimate_classroom_occupancy(multi_bytes, quality_result=q_multi, expected_enrollment=30)
    assert q_multi.quality_status == "GOOD"
    assert res_multi.estimated_count == 6
    assert res_multi.is_uncertain is False
    assert res_multi.confidence_score >= 0.70

