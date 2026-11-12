"""Unit and contract tests for modular RFID hardware extension interface.

Tests Objective 1 (Camera/RFID Capture Pipeline) RFID extension boundary:
- IRfidProvider abstract interface compliance.
- MockRfidProvider reader connection states.
- Successful badge scans and student/cohort resolution.
- Disconnected reader and hardware error handling.
- Invalid hexadecimal UID formats.
- Unregistered card handling.
- Immutability and serialization of RfidScanResult.
"""

import pytest

from attendsure.data.rfid import (
    HEX_UID_REGEX,
    IRfidProvider,
    MockRfidProvider,
    RfidScanResult,
    VALID_RFID_STATUSES,
)


def test_mock_rfid_provider_satisfies_interface():
    """Verify MockRfidProvider is an instance of IRfidProvider."""
    provider = MockRfidProvider()
    assert isinstance(provider, IRfidProvider)
    assert provider.validate_connection()
    assert provider.get_reader_status() == "READER_CONNECTED"


def test_successful_card_scan_resolves_student():
    """Verify scanning a recognized card UID resolves the student and class IDs."""
    provider = MockRfidProvider()
    scan = provider.scan_card(simulated_uid="A1B2C3D4")

    assert scan.status == "SCAN_SUCCESS"
    assert scan.card_uid == "A1B2C3D4"
    assert scan.student_id == "STU-101"
    assert scan.class_id == "CLASS-01-A"
    assert "verified" in scan.diagnostic_message.lower()


def test_disconnected_reader_returns_error_state():
    """Verify provider returns READER_DISCONNECTED when hardware is offline."""
    provider = MockRfidProvider(is_connected=False)
    assert not provider.validate_connection()
    assert provider.get_reader_status() == "READER_DISCONNECTED"

    scan = provider.scan_card(simulated_uid="A1B2C3D4")
    assert scan.status == "READER_DISCONNECTED"
    assert scan.card_uid == ""
    assert scan.student_id is None
    assert "disconnected" in scan.diagnostic_message.lower()


def test_unregistered_card_handled_gracefully():
    """Verify scanning a valid format UID not in school roster returns CARD_NOT_RECOGNIZED."""
    provider = MockRfidProvider()
    unregistered_uid = "99887766"
    scan = provider.scan_card(simulated_uid=unregistered_uid)

    assert scan.status == "CARD_NOT_RECOGNIZED"
    assert scan.card_uid == unregistered_uid
    assert scan.student_id is None
    assert "unassigned" in scan.diagnostic_message.lower()


def test_invalid_uid_format_rejected():
    """Verify malformed non-hexadecimal UIDs are rejected as SCAN_FAILED."""
    provider = MockRfidProvider()

    # Short / non-hex string
    scan_short = provider.scan_card(simulated_uid="SHORT")
    assert scan_short.status == "SCAN_FAILED"
    assert "invalid card uid format" in scan_short.diagnostic_message.lower()

    # Special characters
    scan_special = provider.scan_card(simulated_uid="A1B2-C3D4-!@#$")
    assert scan_special.status == "SCAN_FAILED"


def test_scan_timeout_no_card():
    """Verify null simulated UID simulates a timeout without card presence."""
    provider = MockRfidProvider()
    scan = provider.scan_card(simulated_uid=None)

    assert scan.status == "SCAN_FAILED"
    assert "timed out" in scan.diagnostic_message.lower()


def test_rfid_scan_result_immutability_and_serialization():
    """Verify RfidScanResult dataclass is frozen and serializes to dict."""
    scan = RfidScanResult(
        card_uid="A1B2C3D4",
        timestamp="2026-11-10T09:00:00Z",
        status="SCAN_SUCCESS",
        student_id="STU-101",
        class_id="CLASS-01-A",
        diagnostic_message="Success",
    )

    with pytest.raises(Exception):
        scan.card_uid = "NEW_UID"  # type: ignore[misc]

    d = scan.to_dict()
    assert isinstance(d, dict)
    assert d["card_uid"] == "A1B2C3D4"
    assert d["status"] in VALID_RFID_STATUSES

