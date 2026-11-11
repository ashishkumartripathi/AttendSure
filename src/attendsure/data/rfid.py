"""RFID hardware extension boundary for AttendSure.

Provides a decoupled, modular interface for future RFID scanner hardware integration
adhering to Objective 1 (Camera/RFID Capture Pipeline).

ARCHITECTURAL BOUNDARY & FUTURE HARDWARE NOTICE:
------------------------------------------------
1. This module defines the architectural driver interface and data contract for RFID badge readers.
2. In the current release, physical RFID hardware is designated as FUTURE PRODUCTION SCOPE.
   No physical RFID scanner hardware is currently connected or claimed as tested.
3. The interface allows future USB/Serial or SPI RFID hardware (e.g. RC522, PN532) to be
   plugged in without altering attendance integrity, validation, or anomaly detection pipelines.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Any, Literal, Optional

RfidStatus = Literal[
    "READER_CONNECTED",
    "READER_DISCONNECTED",
    "SCAN_SUCCESS",
    "SCAN_FAILED",
    "CARD_NOT_RECOGNIZED",
]

VALID_RFID_STATUSES: set[str] = {
    "READER_CONNECTED",
    "READER_DISCONNECTED",
    "SCAN_SUCCESS",
    "SCAN_FAILED",
    "CARD_NOT_RECOGNIZED",
}

# Standard 8-character or 14-character hexadecimal UID format for Mifare cards
HEX_UID_REGEX = re.compile(r"^[0-9A-Fa-f]{8,14}$")


@dataclass(frozen=True)
class RfidScanResult:
    """Represents the outcome of an individual student RFID card tap."""

    card_uid: str
    timestamp: str
    status: RfidStatus
    student_id: Optional[str] = None
    class_id: Optional[str] = None
    diagnostic_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IRfidProvider(ABC):
    """Abstract driver interface for RFID badge scanning devices.

    Future hardware implementations (e.g., PySerial USB reader or Raspberry Pi SPI)
    must implement these methods to interface with the AttendSure attendance workflow.
    """

    @abstractmethod
    def get_reader_status(self) -> str:
        """Query the operational state of the RFID reader hardware.

        Returns:
            Status string (e.g., 'READER_CONNECTED' or 'READER_DISCONNECTED').
        """
        pass

    @abstractmethod
    def scan_card(self, timeout_seconds: float = 2.0) -> RfidScanResult:
        """Poll the reader for an active card presence and decode the UID.

        Args:
            timeout_seconds: Duration to wait for a card tap.

        Returns:
            RfidScanResult containing card UID, resolved student metadata, and status.
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Perform a hardware handshake to verify the physical reader is responsive.

        Returns:
            True if reader acknowledges commands, False otherwise.
        """
        pass


class MockRfidProvider(IRfidProvider):
    """Configurable mock RFID provider for testing and software verification.

    Simulates card taps, reader disconnection, and unknown card scenarios without
    requiring physical USB/Serial scanner hardware.
    """

    def __init__(
        self,
        *,
        is_connected: bool = True,
        card_roster: Optional[dict[str, tuple[str, str]]] = None,
    ) -> None:
        """Initialize mock provider.

        Args:
            is_connected: Whether the mock hardware is responsive.
            card_roster: Dictionary mapping card_uid -> (student_id, class_id).
        """
        self._is_connected = is_connected
        # Default mock roster for reproducible testing
        self._card_roster: dict[str, tuple[str, str]] = card_roster or {
            "A1B2C3D4": ("STU-101", "CLASS-01-A"),
            "E5F6A7B8": ("STU-102", "CLASS-01-A"),
            "C9D0E1F2": ("STU-103", "CLASS-02-B"),
        }

    def set_connected(self, connected: bool) -> None:
        """Dynamically toggle the simulated hardware connection status."""
        self._is_connected = connected

    def get_reader_status(self) -> str:
        return "READER_CONNECTED" if self._is_connected else "READER_DISCONNECTED"

    def validate_connection(self) -> bool:
        return self._is_connected

    def scan_card(
        self,
        simulated_uid: Optional[str] = "A1B2C3D4",
        timeout_seconds: float = 2.0,
    ) -> RfidScanResult:
        """Simulate a card tap event.

        Args:
            simulated_uid: UID to present to the reader. If None, simulates timeout/no card.
            timeout_seconds: Timeout parameter (ignored in mock).

        Returns:
            RfidScanResult with contract-compliant metadata.
        """
        now_ts = datetime.now(timezone.utc).isoformat()

        if not self._is_connected:
            return RfidScanResult(
                card_uid="",
                timestamp=now_ts,
                status="READER_DISCONNECTED",
                diagnostic_message="RFID scanner hardware not detected or disconnected.",
            )

        if simulated_uid is None:
            return RfidScanResult(
                card_uid="",
                timestamp=now_ts,
                status="SCAN_FAILED",
                diagnostic_message="Scan timed out: No RFID badge detected on scanner.",
            )

        uid_clean = simulated_uid.strip().upper()
        if not HEX_UID_REGEX.match(uid_clean):
            return RfidScanResult(
                card_uid=uid_clean,
                timestamp=now_ts,
                status="SCAN_FAILED",
                diagnostic_message=f"Invalid card UID format: '{uid_clean}'. Expected 8-14 hex digits.",
            )

        if uid_clean in self._card_roster:
            stu_id, class_id = self._card_roster[uid_clean]
            return RfidScanResult(
                card_uid=uid_clean,
                timestamp=now_ts,
                status="SCAN_SUCCESS",
                student_id=stu_id,
                class_id=class_id,
                diagnostic_message=f"Card verified for student {stu_id} in {class_id}.",
            )
        else:
            return RfidScanResult(
                card_uid=uid_clean,
                timestamp=now_ts,
                status="CARD_NOT_RECOGNIZED",
                diagnostic_message=f"Card UID '{uid_clean}' is unassigned or not in active school roster.",
            )

