"""CSV import and export operations for AttendSure.

Provides robust, row-numbered validation, duplicate collision prevention,
and all-or-nothing/partial import modes conforming to docs/data-contract.md.
"""

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import io
import json
from pathlib import Path
from typing import Any, IO, Optional, Sequence, Union
import uuid

from attendsure.data.models import SessionRecord
from attendsure.data.storage import (
    ALERT_COLUMNS,
    SESSION_COLUMNS,
    AttendanceRepository,
)
from attendsure.data.validation import validate_session_dict

REQUIRED_CSV_COLUMNS = [
    "class_id",
    "session_date",
    "expected_enrollment",
    "present_count",
    "absent_count",
]

OPTIONAL_CSV_COLUMNS = [
    "session_id",
    "webcam_status",
    "webcam_count",
    "record_source",
    "created_at",
]


@dataclass(frozen=True)
class CsvRowError:
    """Represents a validation or collision error for a specific row in a CSV file."""

    line_number: int  # 1-indexed line number in the CSV file (line 1 is header)
    row_index: int  # 0-indexed data row index (first data row is row 0)
    class_id: Optional[str]
    session_date: Optional[str]
    errors: list[str]


@dataclass(frozen=True)
class CsvImportResult:
    """Represents the complete result of a CSV session import operation."""

    total_rows: int
    imported_count: int
    failed_count: int
    errors: list[CsvRowError]
    imported_sessions: list[SessionRecord]
    warnings: list[str]


def _read_csv_content(csv_source: Union[str, Path, IO[str], IO[bytes]]) -> str:
    """Read CSV content into a string, safely handling file paths, strings, and streams."""
    if isinstance(csv_source, Path) or (
        isinstance(csv_source, str)
        and "\n" not in csv_source
        and "\r" not in csv_source
        and Path(csv_source).is_file()
    ):
        with open(str(csv_source), "r", encoding="utf-8-sig") as f:
            return f.read()
    elif isinstance(csv_source, str):
        return csv_source.lstrip("\ufeff")
    elif hasattr(csv_source, "read"):
        raw = csv_source.read()
        if isinstance(raw, bytes):
            return raw.decode("utf-8-sig")
        return str(raw).lstrip("\ufeff")
    else:
        raise TypeError(f"Unsupported csv_source type: {type(csv_source).__name__}.")


def import_sessions_from_csv(
    repo: AttendanceRepository,
    csv_source: Union[str, Path, IO[str], IO[bytes]],
    allow_partial: bool = False,
    dry_run: bool = False,
) -> CsvImportResult:
    """Import attendance sessions from a CSV source with row-level validation.

    Rules:
    - Required columns: class_id, session_date, expected_enrollment, present_count, absent_count.
    - Omitted optional columns are auto-populated with valid defaults:
      session_id (generated UUIDv4), webcam_status ('NOT_ATTEMPTED'),
      webcam_count (None), created_at (current UTC timestamp).
    - record_source is strictly set to 'CSV_IMPORT' regardless of input value.
    - Intra-file duplicates (duplicate session_id or composite class_id/session_date)
      are detected and rejected.
    - Collisions against existing database records are rejected; existing records
      are never silently overwritten.
    - If allow_partial is False (default): all-or-nothing transaction. If any row
      fails validation or collides with stored data, 0 records are written.
    - If allow_partial is True: valid non-colliding rows are persisted in an atomic
      batch, while rejected rows are compiled into structured row errors.
    - If dry_run is True: performs complete parsing, validation, and collision checks
      without persisting any records to the database.

    Args:
        repo: Active AttendanceRepository instance.
        csv_source: File path, CSV text string, or file-like object.
        allow_partial: If True, saves valid rows while returning errors for bad rows;
            if False, aborts all writes if any error is encountered.
        dry_run: If True, returns validation results and candidate sessions without
            writing to the database (default: False).

    Returns:
        CsvImportResult detailing total_rows, imported_count, failed_count, errors,
        persisted sessions, and warnings.

    Raises:
        ValueError: If required columns are missing from the CSV header.
        TypeError: If csv_source is not a recognized type.
    """
    content = _read_csv_content(csv_source)
    if not content.strip():
        return CsvImportResult(
            total_rows=0,
            imported_count=0,
            failed_count=0,
            errors=[],
            imported_sessions=[],
            warnings=[],
        )

    reader = csv.reader(io.StringIO(content))
    header_row = None
    line_num = 0
    for row in reader:
        line_num += 1
        if row and any(cell.strip() for cell in row):
            header_row = row
            break

    if header_row is None:
        return CsvImportResult(
            total_rows=0,
            imported_count=0,
            failed_count=0,
            errors=[],
            imported_sessions=[],
            warnings=[],
        )

    header = [col.strip().lstrip("\ufeff") for col in header_row if col is not None]
    missing_cols = [col for col in REQUIRED_CSV_COLUMNS if col not in header]
    if missing_cols:
        raise ValueError(
            f"CSV import failed: Missing required column(s): {', '.join(missing_cols)}."
        )

    known_cols = set(REQUIRED_CSV_COLUMNS) | set(OPTIONAL_CSV_COLUMNS)
    extra_cols = [col for col in header if col not in known_cols]
    warnings: list[str] = []
    if extra_cols:
        warnings.append(
            f"CSV contains unrecognized column(s) which will be ignored: {', '.join(extra_cols)}."
        )

    raw_data_rows: list[tuple[int, int, dict[str, str]]] = []
    data_idx = 0

    for raw_cells in reader:
        line_num += 1
        # Skip completely blank lines
        if not raw_cells or all(not cell.strip() for cell in raw_cells):
            continue

        row_map = {
            header[i]: raw_cells[i].strip() if i < len(raw_cells) else ""
            for i in range(len(header))
        }
        raw_data_rows.append((line_num, data_idx, row_map))
        data_idx += 1

    total_rows = len(raw_data_rows)
    if total_rows == 0:
        return CsvImportResult(
            total_rows=0,
            imported_count=0,
            failed_count=0,
            errors=[],
            imported_sessions=[],
            warnings=warnings,
        )

    row_errors: list[CsvRowError] = []
    parsed_candidates: list[tuple[int, int, dict[str, Any]]] = []

    # 1. Parse fields and run single-record contract validation
    for l_num, r_idx, row_dict in raw_data_rows:
        errors: list[str] = []

        class_id = row_dict.get("class_id", "").strip()
        session_date = row_dict.get("session_date", "").strip()

        # Parse required integer fields
        def _parse_int(field_name: str) -> Optional[int]:
            val_str = row_dict.get(field_name, "").strip()
            if not val_str:
                errors.append(f"Missing required field '{field_name}'.")
                return None
            try:
                return int(val_str)
            except ValueError:
                errors.append(f"Field '{field_name}' must be an integer, got '{val_str}'.")
                return None

        enrollment = _parse_int("expected_enrollment")
        present = _parse_int("present_count")
        absent = _parse_int("absent_count")

        # Parse optional fields with contract defaults
        sid_str = row_dict.get("session_id", "").strip()
        session_id = sid_str if sid_str else str(uuid.uuid4())

        webcam_status = row_dict.get("webcam_status", "").strip() or "NOT_ATTEMPTED"

        wc_str = row_dict.get("webcam_count", "").strip()
        webcam_count: Optional[int] = None
        if wc_str:
            try:
                webcam_count = int(wc_str)
            except ValueError:
                errors.append(f"Field 'webcam_count' must be an integer, got '{wc_str}'.")
        else:
            webcam_count = None

        ca_str = row_dict.get("created_at", "").strip()
        created_at = ca_str if ca_str else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        candidate_record = {
            "session_id": session_id,
            "class_id": class_id,
            "session_date": session_date,
            "expected_enrollment": enrollment,
            "present_count": present,
            "absent_count": absent,
            "webcam_status": webcam_status,
            "webcam_count": webcam_count,
            "record_source": "CSV_IMPORT",  # Force CSV_IMPORT origin
            "created_at": created_at,
        }

        # Run domain validation if basic parsing didn't fail
        if not errors:
            val_result = validate_session_dict(candidate_record)
            if not val_result.is_valid:
                errors.extend(val_result.errors)

        if errors:
            row_errors.append(
                CsvRowError(
                    line_number=l_num,
                    row_index=r_idx,
                    class_id=class_id or None,
                    session_date=session_date or None,
                    errors=errors,
                )
            )
        else:
            parsed_candidates.append((l_num, r_idx, candidate_record))

    # 2. Intra-file duplicate detection among valid candidates
    seen_class_dates: dict[tuple[str, str], int] = {}
    seen_session_ids: dict[str, int] = {}
    intra_valid_candidates: list[tuple[int, int, dict[str, Any]]] = []

    for l_num, r_idx, candidate in parsed_candidates:
        dup_errors: list[str] = []
        cd_pair = (candidate["class_id"], candidate["session_date"])
        if cd_pair in seen_class_dates:
            dup_errors.append(
                f"Duplicate (class_id, session_date) '{cd_pair}' already seen at line {seen_class_dates[cd_pair]}."
            )
        else:
            seen_class_dates[cd_pair] = l_num

        sid = candidate["session_id"]
        if sid in seen_session_ids:
            dup_errors.append(
                f"Duplicate session_id '{sid}' already seen at line {seen_session_ids[sid]}."
            )
        else:
            seen_session_ids[sid] = l_num

        if dup_errors:
            row_errors.append(
                CsvRowError(
                    line_number=l_num,
                    row_index=r_idx,
                    class_id=candidate["class_id"],
                    session_date=candidate["session_date"],
                    errors=dup_errors,
                )
            )
        else:
            intra_valid_candidates.append((l_num, r_idx, candidate))

    # 3. Database collision checks against existing stored sessions
    conn = repo.get_connection()
    cur = conn.execute("SELECT class_id, session_date, session_id FROM attendance_sessions")
    db_rows = cur.fetchall()
    existing_pairs = {(r["class_id"], r["session_date"]) for r in db_rows}
    existing_ids = {r["session_id"] for r in db_rows}

    final_valid_records: list[SessionRecord] = []

    for l_num, r_idx, candidate in intra_valid_candidates:
        collision_errors: list[str] = []
        cd_pair = (candidate["class_id"], candidate["session_date"])
        if cd_pair in existing_pairs:
            collision_errors.append(
                f"Record for class '{candidate['class_id']}' on date '{candidate['session_date']}' "
                "already exists in database."
            )

        sid = candidate["session_id"]
        if sid in existing_ids:
            collision_errors.append(f"Session ID '{sid}' already exists in database.")

        if collision_errors:
            row_errors.append(
                CsvRowError(
                    line_number=l_num,
                    row_index=r_idx,
                    class_id=candidate["class_id"],
                    session_date=candidate["session_date"],
                    errors=collision_errors,
                )
            )
        else:
            final_valid_records.append(
                SessionRecord(
                    session_id=str(candidate["session_id"]),
                    class_id=str(candidate["class_id"]),
                    session_date=str(candidate["session_date"]),
                    expected_enrollment=int(candidate["expected_enrollment"]),
                    present_count=int(candidate["present_count"]),
                    absent_count=int(candidate["absent_count"]),
                    webcam_status=candidate["webcam_status"],
                    webcam_count=candidate["webcam_count"],
                    record_source=candidate["record_source"],
                    created_at=str(candidate["created_at"]),
                )
            )

    # Sort errors stably by line_number
    row_errors.sort(key=lambda e: e.line_number)

    # 4. Persistence by mode
    if not allow_partial:
        # All-or-nothing mode: if any row failed or collided, persist nothing
        if row_errors:
            return CsvImportResult(
                total_rows=total_rows,
                imported_count=0,
                failed_count=len(row_errors),
                errors=row_errors,
                imported_sessions=[],
                warnings=warnings,
            )
        # All rows valid: persist atomically unless dry_run
        if dry_run:
            saved = final_valid_records
        else:
            saved = repo.save_sessions(final_valid_records)
        return CsvImportResult(
            total_rows=total_rows,
            imported_count=len(saved),
            failed_count=0,
            errors=[],
            imported_sessions=saved,
            warnings=warnings,
        )
    else:
        # Partial mode: persist valid non-colliding records atomically unless dry_run
        if final_valid_records:
            if dry_run:
                saved = final_valid_records
            else:
                saved = repo.save_sessions(final_valid_records)
        else:
            saved = []

        return CsvImportResult(
            total_rows=total_rows,
            imported_count=len(saved),
            failed_count=len(row_errors),
            errors=row_errors,
            imported_sessions=saved,
            warnings=warnings,
        )


def preview_sessions_from_csv(
    repo: AttendanceRepository,
    csv_source: Union[str, Path, IO[str], IO[bytes]],
    allow_partial: bool = False,
) -> CsvImportResult:
    """Validate and preview sessions from CSV without writing to the database.

    Runs exact CSV parsing, domain validation, intra-file duplicate detection,
    and database collision checking without persisting records to SQLite.

    Args:
        repo: Active AttendanceRepository instance for collision checks.
        csv_source: File path, CSV text string, or file-like object.
        allow_partial: If True, previews valid non-colliding rows while listing errors;
            if False, previews all-or-nothing acceptance criteria.

    Returns:
        CsvImportResult detailing total_rows, imported_count (would be imported),
        failed_count, errors, candidate sessions, and warnings.
    """
    return import_sessions_from_csv(repo, csv_source, allow_partial=allow_partial, dry_run=True)


def export_sessions_to_csv(
    repo: AttendanceRepository,
    class_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """Export stored attendance sessions to a standard CSV string.

    Output contains all 10 standard SessionRecord contract fields:
    session_id, class_id, session_date, expected_enrollment, present_count,
    absent_count, webcam_status, webcam_count, record_source, created_at.

    Args:
        repo: Active AttendanceRepository instance.
        class_id: Optional classroom filter.
        start_date: Optional start date filter (inclusive).
        end_date: Optional end date filter (inclusive).

    Returns:
        CSV formatted string suitable for downloads or file storage.
    """
    sessions = repo.get_sessions(class_id=class_id, start_date=start_date, end_date=end_date)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")

    writer.writerow(SESSION_COLUMNS)
    for s in sessions:
        writer.writerow(
            [
                s.session_id,
                s.class_id,
                s.session_date,
                s.expected_enrollment,
                s.present_count,
                s.absent_count,
                s.webcam_status,
                "" if s.webcam_count is None else s.webcam_count,
                s.record_source,
                s.created_at,
            ]
        )

    return buffer.getvalue()


def export_alerts_to_csv(
    repo: AttendanceRepository,
    review_status: Optional[str] = None,
    class_id: Optional[str] = None,
    rule_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """Export stored anomaly alerts to a standardized CSV string.

    Outputs all 13 standard Alert fields with structured metrics deterministically
    serialized as JSON strings and safely escaped per RFC 4180.

    Args:
        repo: Active AttendanceRepository instance.
        review_status: Optional review status filter.
        class_id: Optional classroom filter.
        rule_id: Optional rule filter.
        start_date: Optional start date filter (inclusive).
        end_date: Optional end date filter (inclusive).

    Returns:
        CSV formatted string suitable for educator audit reports and downloads.
    """
    alerts = repo.get_alerts(
        review_status=review_status,
        class_id=class_id,
        rule_id=rule_id,
        start_date=start_date,
        end_date=end_date,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")

    writer.writerow(ALERT_COLUMNS)
    for a in alerts:
        writer.writerow(
            [
                a.alert_id,
                a.session_id,
                a.class_id,
                a.session_date,
                a.rule_id,
                a.rule_title,
                a.priority,
                json.dumps(a.observed_value, sort_keys=True),
                json.dumps(a.baseline_reference, sort_keys=True),
                json.dumps(a.threshold_applied, sort_keys=True),
                a.explanation,
                a.review_status,
                a.created_at,
            ]
        )

    return buffer.getvalue()
