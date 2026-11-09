"""Simulated visible-person webcam counter for AttendSure.

Implements the Phase 1 simulated webcam person-counter interface conforming to
docs/data-contract.md Section 3.2, Section 5.3, and Section 7.

Design Principles:
------------------
1. Privacy First: No physical camera access, image storage, biometric capture,
   or facial recognition. Operates purely as a synthetic numerical estimator.
2. Decision Support, Never Accusation: A camera discrepancy is strictly an
   evidence-backed review signal, never proof of fraud or misconduct.
3. Status and Count Invariants:
   - When status == "SUCCESS", estimated_count must be an integer >= 0.
   - When status != "SUCCESS" (CAMERA_UNAVAILABLE, NOT_ATTEMPTED, DETECTION_FAILED),
     estimated_count must be None.
4. Optional Verification Aid: Degradation or absence of the camera module never
   invalidates or mutates manually recorded attendance.
"""

import math
import random
from typing import Literal, Optional

from attendsure.data.models import WebcamCounterResult, WebcamStatus

SimulatedWebcamMode = Literal[
    "NORMAL",
    "CAMERA_OFFLINE",
    "DISCREPANCY",
    "MINOR_DISCREPANCY",
    "DETECTION_FAILED",
    "NOT_ATTEMPTED",
]

ALLOWED_MODES: set[str] = {
    "NORMAL",
    "CAMERA_OFFLINE",
    "CAMERA_UNAVAILABLE",
    "DISCREPANCY",
    "MINOR_DISCREPANCY",
    "BELOW_THRESHOLD",
    "DETECTION_FAILED",
    "NOT_ATTEMPTED",
}


def get_simulated_webcam_count(
    mode: str = "NORMAL",
    reference_present: int = 30,
    *,
    delta: Optional[int] = None,
    confidence_score: Optional[float] = None,
    random_seed: Optional[int] = None,
) -> WebcamCounterResult:
    """Simulate visible-person webcam estimation results without physical hardware.

    Conforms to docs/data-contract.md Section 7 mock counter interface.
    Generates controlled mock results for normal attendance verification,
    camera degradation/offline conditions, and visible-person discrepancies.

    Args:
        mode: Simulation scenario mode:
            - "NORMAL": Successful camera count closely aligning with manual roll call.
            - "DISCREPANCY": Successful camera count exceeding discrepancy thresholds
              (relative diff >= 20% and absolute diff >= 5).
            - "MINOR_DISCREPANCY" (or "BELOW_THRESHOLD"): Successful count with minor variation
              staying below alert trigger thresholds.
            - "CAMERA_OFFLINE" (or "CAMERA_UNAVAILABLE"): Hardware unavailable/disconnected.
            - "DETECTION_FAILED": Capture succeeded but CV estimation failed (e.g. lens blocked).
            - "NOT_ATTEMPTED": Camera capture was not attempted.
        reference_present: Recorded manual present student count (must be non-negative).
        delta: Optional explicit integer offset added to reference_present for SUCCESS modes.
        confidence_score: Optional custom confidence float in [0.0, 1.0].
        random_seed: Optional random seed for deterministic tracking noise simulation.

    Returns:
        WebcamCounterResult containing:
            - status: WebcamStatus ("SUCCESS", "CAMERA_UNAVAILABLE", etc.)
            - estimated_count: Non-negative int if SUCCESS, else None.
            - confidence_score: Float in [0.0, 1.0] if SUCCESS, else None.
            - diagnostic_message: Clear, non-accusatory operational explanation.

    Raises:
        TypeError: If reference_present is not an integer.
        TypeError: If delta is not an integer.
        ValueError: If reference_present is negative.
        ValueError: If mode is not an allowed simulation mode.
        ValueError: If confidence_score is not in [0.0, 1.0].
    """
    if not isinstance(reference_present, int) or isinstance(reference_present, bool):
        raise TypeError(
            f"reference_present must be an integer, got {type(reference_present).__name__}."
        )

    if reference_present < 0:
        raise ValueError(
            f"reference_present must be non-negative, got {reference_present}."
        )

    if not isinstance(mode, str):
        raise TypeError(f"mode must be a string, got {type(mode).__name__}.")

    normalized_mode = mode.strip().upper()
    if normalized_mode not in ALLOWED_MODES:
        raise ValueError(
            f"Invalid mode '{mode}'. Allowed modes: {sorted(ALLOWED_MODES)}."
        )

    if delta is not None:
        if not isinstance(delta, int) or isinstance(delta, bool):
            raise TypeError(
                f"delta must be an integer, got {type(delta).__name__}."
            )

    if confidence_score is not None:
        if not isinstance(confidence_score, (int, float)) or isinstance(confidence_score, bool):
            raise TypeError(
                f"confidence_score must be a float, got {type(confidence_score).__name__}."
            )
        if not (0.0 <= float(confidence_score) <= 1.0):
            raise ValueError(
                f"confidence_score must be between 0.0 and 1.0, got {confidence_score}."
            )

    # -------------------------------------------------------------------------
    # 1. Hardware Fallback / Non-Success Modes (Invariants: count=None, conf=None)
    # -------------------------------------------------------------------------
    if normalized_mode in ("CAMERA_OFFLINE", "CAMERA_UNAVAILABLE"):
        return WebcamCounterResult(
            status="CAMERA_UNAVAILABLE",
            estimated_count=None,
            confidence_score=None,
            diagnostic_message=(
                "Camera hardware is offline or unavailable. "
                "Visible-person estimation was not performed. "
                "Manual attendance remains valid."
            ),
        )

    if normalized_mode == "DETECTION_FAILED":
        return WebcamCounterResult(
            status="DETECTION_FAILED",
            estimated_count=None,
            confidence_score=None,
            diagnostic_message=(
                "Visible-person estimation could not be completed "
                "(e.g., camera obstructed, lighting insufficient). "
                "Manual attendance remains valid."
            ),
        )

    if normalized_mode == "NOT_ATTEMPTED":
        return WebcamCounterResult(
            status="NOT_ATTEMPTED",
            estimated_count=None,
            confidence_score=None,
            diagnostic_message=(
                "Webcam person-counting was not attempted for this session. "
                "Manual attendance remains valid."
            ),
        )

    # -------------------------------------------------------------------------
    # 2. Successful Estimation Modes (Status: SUCCESS, count >= 0)
    # -------------------------------------------------------------------------
    rng = random.Random(random_seed) if random_seed is not None else None

    if delta is not None:
        computed_count = max(0, reference_present + delta)
        conf = float(confidence_score) if confidence_score is not None else 0.90
        abs_diff = abs(computed_count - reference_present)
        rel_diff = (abs_diff / reference_present * 100.0) if reference_present > 0 else 0.0
        msg = (
            f"Visible-person count estimation completed (difference: {abs_diff} people, "
            f"{rel_diff:.1f}% relative difference)."
        )
        return WebcamCounterResult(
            status="SUCCESS",
            estimated_count=computed_count,
            confidence_score=conf,
            diagnostic_message=msg,
        )

    if normalized_mode in ("MINOR_DISCREPANCY", "BELOW_THRESHOLD"):
        # Benign variation staying strictly below alert threshold (abs_diff < 5)
        sub_delta = -2 if reference_present >= 2 else 2
        computed_count = max(0, reference_present + sub_delta)
        conf = float(confidence_score) if confidence_score is not None else 0.92
        return WebcamCounterResult(
            status="SUCCESS",
            estimated_count=computed_count,
            confidence_score=conf,
            diagnostic_message=(
                "Visible-person count estimation completed with minor variance "
                "within normal operational bounds."
            ),
        )

    if normalized_mode == "DISCREPANCY":
        # Discrepancy mode: exceeds both absolute threshold (>= 5) and relative threshold (>= 20%)
        from attendsure.detection.rules import (
            DEFAULT_WEBCAM_ABS_THRESHOLD,
            DEFAULT_WEBCAM_REL_THRESHOLD_PCT,
        )
        conf = float(confidence_score) if confidence_score is not None else 0.85
        if reference_present == 0:
            computed_count = DEFAULT_WEBCAM_ABS_THRESHOLD + 1  # 6, guaranteeing abs_diff >= 5
        else:
            rel_gap = int(math.ceil(reference_present * (DEFAULT_WEBCAM_REL_THRESHOLD_PCT + 5.0) / 100.0))
            gap = max(DEFAULT_WEBCAM_ABS_THRESHOLD, rel_gap)
            if reference_present - gap >= 0:
                computed_count = reference_present - gap
            else:
                computed_count = reference_present + gap

        return WebcamCounterResult(
            status="SUCCESS",
            estimated_count=computed_count,
            confidence_score=conf,
            diagnostic_message=(
                "Visible-person count estimation completed with a notable discrepancy "
                "relative to manual attendance. Discrepancies may arise naturally from "
                "camera placement, physical occlusion, or students outside the camera's view."
            ),
        )

    # Default "NORMAL" mode: closely aligns with reference_present
    conf = float(confidence_score) if confidence_score is not None else 0.95
    if rng is not None and reference_present > 3:
        tracking_noise = rng.choice([-1, 0, 1])
        computed_count = max(0, reference_present + tracking_noise)
    else:
        computed_count = reference_present

    return WebcamCounterResult(
        status="SUCCESS",
        estimated_count=computed_count,
        confidence_score=conf,
        diagnostic_message=(
            "Visible-person count estimation completed successfully. "
            "Estimated count aligns closely with manual attendance."
        ),
    )
