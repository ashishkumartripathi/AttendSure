"""Unit and integration tests for AttendSure CSV import and export operations.

Verifies column validation, exact row-numbered error reporting, UUID generation,
record_source enforcement, intra-file duplicates, database collisions, all-or-nothing
and partial import modes, and export round-trip compatibility.
"""

import csv
import io
from pathlib import Path
import sqlite3
import pytest

from attendsure.data.csv_io import (
    CsvImportResult,
    CsvRowError,
    export_alerts_to_csv,
    export_sessions_to_csv,
    import_sessions_from_csv,
    preview_sessions_from_csv,
)
from attendsure.data.models import Alert, SessionRecord
from attendsure.data.storage import AttendanceRepository


@pytest.fixture
def repo(tmp_path):
    """Provide an isolated file-based AttendanceRepository for testing."""
    db_file = tmp_path / "test_csv.db"
    repository = AttendanceRepository(db_path=db_file)
    yield repository
    repository.close()


def test_valid_csv_import_all_or_nothing(repo):
    """1. Valid CSV import persists all records with all-or-nothing mode."""
    csv_text = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
CLASS-01-A,2026-10-21,30,27,3
CLASS-02-B,2026-10-20,25,24,1
"""
    result = import_sessions_from_csv(repo, csv_text)

    assert isinstance(result, CsvImportResult)
    assert result.total_rows == 3
    assert result.imported_count == 3
    assert result.failed_count == 0
    assert result.errors == []
    assert len(result.imported_sessions) == 3

    # Check persistence in database
    sessions = repo.get_sessions()
    assert len(sessions) == 3
    assert {s.class_id for s in sessions} == {"CLASS-01-A", "CLASS-02-B"}


def test_csv_missing_required_columns_rejected(repo):
    """2. CSV missing required columns raises ValueError with missing column names."""
    bad_csv = """class_id,session_date,expected_enrollment
CLASS-01-A,2026-10-20,30
"""
    with pytest.raises(ValueError, match="Missing required column\\(s\\): present_count, absent_count"):
        import_sessions_from_csv(repo, bad_csv)

    assert len(repo.get_sessions()) == 0


def test_csv_invalid_counts_dates_and_row_numbered_errors(repo):
    """3 & 4. Invalid counts/dates generate exact row-numbered errors counting header as line 1."""
    csv_text = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
CLASS-01-A,2026-02-31,30,28,2
CLASS-02-B,2026-10-20,30,20,5
CLASS-03-C,2026-10-20,30,-5,35
"""
    result = import_sessions_from_csv(repo, csv_text, allow_partial=False)

    # All-or-nothing: 0 imported, 3 failed rows
    assert result.total_rows == 4
    assert result.imported_count == 0
    assert result.failed_count == 3
    assert len(result.errors) == 3
    assert len(repo.get_sessions()) == 0

    err_map = {e.line_number: e for e in result.errors}

    # Line 3 (row 1): invalid date 2026-02-31
    assert 3 in err_map
    assert err_map[3].row_index == 1
    assert err_map[3].class_id == "CLASS-01-A"
    assert any("not a valid calendar date" in msg for msg in err_map[3].errors)

    # Line 4 (row 2): 20 + 5 != 30
    assert 4 in err_map
    assert err_map[4].row_index == 2
    assert err_map[4].class_id == "CLASS-02-B"
    assert any("present_count + absent_count" in msg for msg in err_map[4].errors)

    # Line 5 (row 3): negative present_count (-5)
    assert 5 in err_map
    assert err_map[5].row_index == 3
    assert err_map[5].class_id == "CLASS-03-C"
    assert any("present_count" in msg for msg in err_map[5].errors)


def test_csv_missing_optional_values_and_generated_uuid(repo):
    """5. Missing optional values are auto-populated with contract defaults and UUIDv4."""
    csv_text = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
"""
    result = import_sessions_from_csv(repo, csv_text)
    assert result.imported_count == 1

    session = result.imported_sessions[0]
    assert len(session.session_id) == 36  # Standard UUID format
    assert session.webcam_status == "NOT_ATTEMPTED"
    assert session.webcam_count is None
    assert session.created_at.endswith("Z")


def test_csv_record_source_always_csv_import(repo):
    """6. record_source is strictly set to 'CSV_IMPORT' regardless of supplied CSV value."""
    csv_text = """class_id,session_date,expected_enrollment,present_count,absent_count,record_source
CLASS-01-A,2026-10-20,30,28,2,MANUAL_ENTRY
CLASS-02-A,2026-10-20,30,28,2,SYNTHETIC
"""
    result = import_sessions_from_csv(repo, csv_text)
    assert result.imported_count == 2
    for s in result.imported_sessions:
        assert s.record_source == "CSV_IMPORT"

    stored = repo.get_sessions()
    for s in stored:
        assert s.record_source == "CSV_IMPORT"


def test_csv_intra_file_duplicate_rejection(repo):
    """7. Duplicate rows within the same CSV are rejected."""
    csv_text = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
CLASS-01-A,2026-10-20,30,27,3
"""
    result = import_sessions_from_csv(repo, csv_text)
    assert result.imported_count == 0
    assert result.failed_count == 1
    assert result.errors[0].line_number == 3
    assert "Duplicate (class_id, session_date)" in result.errors[0].errors[0]
    assert len(repo.get_sessions()) == 0


def test_csv_existing_database_collision_prevention(repo):
    """8. Existing database records are not overwritten by colliding CSV rows."""
    # Pre-populate database with Day 20 record (present = 29)
    existing_session = SessionRecord(
        session_id="550e8400-e29b-41d4-a716-446655440001",
        class_id="CLASS-01-A",
        session_date="2026-10-20",
        expected_enrollment=30,
        present_count=29,
        absent_count=1,
        webcam_status="NOT_ATTEMPTED",
        webcam_count=None,
        record_source="MANUAL_ENTRY",
        created_at="2026-10-20T09:00:00Z",
    )
    repo.save_session(existing_session)

    # Attempt to import CSV with colliding class/date (present = 20)
    csv_text = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,20,10
CLASS-02-B,2026-10-21,25,24,1
"""
    result = import_sessions_from_csv(repo, csv_text, allow_partial=False)

    # All-or-nothing mode: aborts entire import
    assert result.imported_count == 0
    assert result.failed_count == 1
    assert result.errors[0].line_number == 2
    assert "already exists in database" in result.errors[0].errors[0]

    # Stored record must NOT have been overwritten
    stored = repo.get_session_by_id(existing_session.session_id)
    assert stored.present_count == 29
    assert len(repo.get_sessions()) == 1


def test_csv_all_or_nothing_rollback_on_single_error(repo):
    """9. All-or-nothing mode writes 0 records when any single row fails."""
    csv_text = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
CLASS-01-A,2026-10-21,30,28,2
CLASS-01-A,2026-10-22,30,99,2
"""
    result = import_sessions_from_csv(repo, csv_text, allow_partial=False)
    assert result.imported_count == 0
    assert result.failed_count == 1
    assert len(repo.get_sessions()) == 0


def test_csv_partial_import_mode(repo):
    """10. Partial import mode persists valid rows and reports rejected rows."""
    csv_text = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
CLASS-01-A,2026-10-21,30,99,2
CLASS-02-B,2026-10-22,25,24,1
"""
    result = import_sessions_from_csv(repo, csv_text, allow_partial=True)

    assert result.total_rows == 3
    assert result.imported_count == 2
    assert result.failed_count == 1
    assert len(result.errors) == 1
    assert result.errors[0].line_number == 3

    # The 2 valid rows are persisted in database
    stored = repo.get_sessions()
    assert len(stored) == 2
    assert {s.class_id for s in stored} == {"CLASS-01-A", "CLASS-02-B"}


def test_export_sessions_to_csv(repo):
    """11. export_sessions_to_csv formats 10 contract columns with filtering and empty state."""
    # Empty export
    empty_csv = export_sessions_to_csv(repo)
    assert empty_csv.strip() == "session_id,class_id,session_date,expected_enrollment,present_count,absent_count,webcam_status,webcam_count,record_source,created_at"

    # Add 2 sessions
    s1 = SessionRecord("550e8400-e29b-41d4-a716-446655440001", "CLASS-01-A", "2026-10-20", 30, 28, 2, "NOT_ATTEMPTED", None, "MANUAL_ENTRY", "2026-10-20T09:00:00Z")
    s2 = SessionRecord("550e8400-e29b-41d4-a716-446655440002", "CLASS-02-A", "2026-10-21", 25, 20, 5, "SUCCESS", 21, "CSV_IMPORT", "2026-10-21T09:00:00Z")
    repo.save_sessions([s1, s2])

    exported = export_sessions_to_csv(repo)
    lines = [line.strip() for line in exported.strip().splitlines()]
    assert len(lines) == 3
    assert "CLASS-01-A" in lines[1]
    assert "CLASS-02-A" in lines[2]
    assert ",21," in lines[2]  # webcam_count = 21

    # Filtered export
    filtered = export_sessions_to_csv(repo, class_id="CLASS-01-A")
    filtered_lines = [l.strip() for l in filtered.strip().splitlines()]
    assert len(filtered_lines) == 2
    assert "CLASS-01-A" in filtered_lines[1]


def test_export_alerts_to_csv_and_escaping(repo):
    """11. export_alerts_to_csv serializes JSON metrics and escapes commas and quotes."""
    s = SessionRecord("550e8400-e29b-41d4-a716-446655440001", "CLASS-01-A", "2026-10-20", 30, 10, 20, "NOT_ATTEMPTED", None, "MANUAL_ENTRY", "2026-10-20T09:00:00Z")
    repo.save_session(s)

    alert = Alert(
        alert_id="ALT-001",
        session_id=s.session_id,
        class_id=s.class_id,
        session_date=s.session_date,
        rule_id="RULE_ATTENDANCE_DROP",
        rule_title="Unusual Attendance Drop",
        priority="REVIEW_REQUIRED",
        observed_value={"present_count": 10, "rate_pct": 33.3},
        baseline_reference={"median_rate_pct": 90.0},
        threshold_applied={"threshold_pct": 30.0},
        explanation='Attendance dropped sharply; teacher noted: "seasonal rains, transit disruption".',
        review_status="PENDING_REVIEW",
        created_at="2026-10-20T10:00:00Z",
    )
    repo.save_alerts([alert])

    exported = export_alerts_to_csv(repo)
    assert "ALT-001" in exported
    assert "RULE_ATTENDANCE_DROP" in exported
    # Explanation with quotes must be properly CSV-escaped
    assert 'seasonal rains, transit disruption' in exported


def test_csv_export_import_round_trip(repo, tmp_path):
    """12. Session CSV export and re-import preserves all contract fields."""
    s = SessionRecord(
        session_id="550e8400-e29b-41d4-a716-446655440001",
        class_id="CLASS-01-A",
        session_date="2026-10-20",
        expected_enrollment=30,
        present_count=28,
        absent_count=2,
        webcam_status="NOT_ATTEMPTED",
        webcam_count=None,
        record_source="MANUAL_ENTRY",
        created_at="2026-10-20T09:00:00Z",
    )
    repo.save_session(s)

    exported_csv = export_sessions_to_csv(repo)

    # Import exported CSV into a fresh repository
    repo2 = AttendanceRepository(db_path=tmp_path / "round_trip.db")
    import_res = import_sessions_from_csv(repo2, exported_csv)

    assert import_res.imported_count == 1
    reloaded = repo2.get_session_by_id(s.session_id)
    assert reloaded is not None
    assert reloaded.class_id == s.class_id
    assert reloaded.session_date == s.session_date
    assert reloaded.expected_enrollment == s.expected_enrollment
    assert reloaded.present_count == s.present_count
    assert reloaded.absent_count == s.absent_count
    assert reloaded.record_source == "CSV_IMPORT"  # forced to CSV_IMPORT on import
    repo2.close()


def test_csv_extra_columns_ignored_with_warning(repo):
    """13. Extra unknown columns are ignored and reported in informational warnings."""
    csv_text = """class_id,session_date,expected_enrollment,present_count,absent_count,teacher_name,weather_notes
CLASS-01-A,2026-10-20,30,28,2,Mr. Sharma,Clear skies
"""
    result = import_sessions_from_csv(repo, csv_text)
    assert result.imported_count == 1
    assert len(result.warnings) == 1
    assert "teacher_name" in result.warnings[0]
    assert "weather_notes" in result.warnings[0]


def test_csv_import_required_cell_blank_reported_with_line_number(repo):
    """5. Verify that a CSV with a blank cell in a required column produces a structured row error."""
    csv_text = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
CLASS-01-A,2026-10-21,30,,2
"""
    result = import_sessions_from_csv(repo, csv_text, allow_partial=False)
    assert result.total_rows == 2
    assert result.imported_count == 0
    assert result.failed_count == 1
    assert len(result.errors) == 1

    err = result.errors[0]
    assert err.line_number == 3
    assert err.row_index == 1
    assert err.class_id == "CLASS-01-A"
    assert any("Missing required field 'present_count'" in msg for msg in err.errors)
    assert len(repo.get_sessions()) == 0


def test_csv_import_non_integer_numeric_field_reported(repo):
    """6. Verify non-integer strings in numeric columns fail with clear row-level errors."""
    csv_text = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,twenty-eight,2
"""
    result = import_sessions_from_csv(repo, csv_text, allow_partial=False)
    assert result.total_rows == 1
    assert result.imported_count == 0
    assert result.failed_count == 1
    assert len(result.errors) == 1

    err = result.errors[0]
    assert err.line_number == 2
    assert err.row_index == 0
    assert any(
        "Field 'present_count' must be an integer, got 'twenty-eight'" in msg
        for msg in err.errors
    )
    assert len(repo.get_sessions()) == 0


def test_csv_import_duplicate_session_id_on_different_classes_rejected(repo):
    """7. Verify duplicate session_id is rejected even if class_id and session_date differ."""
    dup_uuid = "550e8400-e29b-41d4-a716-446655440099"
    csv_text = f"""session_id,class_id,session_date,expected_enrollment,present_count,absent_count
{dup_uuid},CLASS-01-A,2026-10-20,30,28,2
{dup_uuid},CLASS-02-B,2026-10-21,25,24,1
"""
    # In all-or-nothing mode: rejects whole file
    res_all = import_sessions_from_csv(repo, csv_text, allow_partial=False)
    assert res_all.imported_count == 0
    assert res_all.failed_count == 1
    assert res_all.errors[0].line_number == 3
    assert f"Duplicate session_id '{dup_uuid}' already seen at line 2" in res_all.errors[0].errors[0]
    assert len(repo.get_sessions()) == 0

    # In partial mode: line 2 is imported, line 3 is rejected
    res_part = import_sessions_from_csv(repo, csv_text, allow_partial=True)
    assert res_part.imported_count == 1
    assert res_part.failed_count == 1
    assert res_part.errors[0].line_number == 3
    assert len(repo.get_sessions()) == 1
    stored = repo.get_sessions()[0]
    assert stored.session_id == dup_uuid
    assert stored.class_id == "CLASS-01-A"


def test_csv_partial_import_rolls_back_on_database_write_failure(repo):
    """8. Verify partial import rolls back the entire batch if a database write error occurs."""
    conn = repo.get_connection()
    # Create a database trigger that aborts writes for class_id 'FAIL_TRIGGER'
    conn.execute(
        """
        CREATE TRIGGER test_abort_insert
        BEFORE INSERT ON attendance_sessions
        WHEN NEW.class_id = 'FAIL_TRIGGER'
        BEGIN
            SELECT RAISE(ABORT, 'Simulated database storage failure');
        END;
        """
    )

    csv_text = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
FAIL_TRIGGER,2026-10-21,30,28,2
"""
    # Both rows pass CSV parsing and intra-batch checks, but database write fails
    with pytest.raises(sqlite3.IntegrityError, match="Simulated database storage failure"):
        import_sessions_from_csv(repo, csv_text, allow_partial=True)

    # Verify atomic rollback: zero records remain in database (CLASS-01-A rolled back)
    assert len(repo.get_sessions()) == 0


def test_csv_export_import_preserves_quotes_commas_and_newlines(repo):
    """9. Verify CSV export and parsing preserves quotes, commas, and embedded newlines."""
    # 1. Session export/re-import with quotes and commas in CSV input
    csv_input = '''"class_id","session_date","expected_enrollment","present_count","absent_count"
"CLASS-01-A","2026-10-20","30","28","2"
'''
    res = import_sessions_from_csv(repo, csv_input)
    assert res.imported_count == 1
    session = res.imported_sessions[0]

    # 2. Alert with explanation containing quotes, commas, and embedded newlines
    multiline_explanation = (
        'Teacher review notes:\n'
        '- "Seasonal monsoon flooding in low-lying area",\n'
        '- Bus transit suspended for routes #4, #5.'
    )
    alert = Alert(
        alert_id="ALT-SPECIAL-01",
        session_id=session.session_id,
        class_id=session.class_id,
        session_date=session.session_date,
        rule_id="RULE_ATTENDANCE_DROP",
        rule_title="Unusual Attendance Drop",
        priority="REVIEW_REQUIRED",
        observed_value={"present_count": 28, "rate_pct": 93.3},
        baseline_reference={"median_rate_pct": 95.0},
        threshold_applied={"threshold_pct": 30.0},
        explanation=multiline_explanation,
        review_status="PENDING_REVIEW",
        created_at="2026-10-20T10:00:00Z",
    )
    repo.save_alerts([alert])

    # Export alerts to CSV
    exported_alerts_csv = export_alerts_to_csv(repo)

    # Parse back using standard RFC 4180 csv reader
    reader = csv.reader(io.StringIO(exported_alerts_csv))
    header = next(reader)
    assert header[10] == "explanation"
    data_rows = list(reader)
    assert len(data_rows) == 1
    reloaded_explanation = data_rows[0][10]

    # Verify exact preservation of quotes, commas, and embedded newlines
    assert reloaded_explanation == multiline_explanation
    assert "\n" in reloaded_explanation
    assert '"' in reloaded_explanation
    assert "," in reloaded_explanation


def test_csv_duplicate_rows_do_not_overwrite_or_duplicate_stored_records(repo):
    """10. Verify importing duplicate rows never overwrites or duplicates existing records."""
    # Seed stored record: Day 20 with present_count = 29
    initial_session = SessionRecord(
        session_id="550e8400-e29b-41d4-a716-446655440001",
        class_id="CLASS-01-A",
        session_date="2026-10-20",
        expected_enrollment=30,
        present_count=29,
        absent_count=1,
        webcam_status="NOT_ATTEMPTED",
        webcam_count=None,
        record_source="MANUAL_ENTRY",
        created_at="2026-10-20T09:00:00Z",
    )
    repo.save_session(initial_session)
    assert len(repo.get_sessions()) == 1

    # CSV contains:
    # - Row 1 & 2: duplicate of stored CLASS-01-A on 2026-10-20 with DIFFERENT present_count (15)
    # - Row 3: new valid session for CLASS-02-B on 2026-10-21
    csv_text = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,15,15
CLASS-01-A,2026-10-20,30,15,15
CLASS-02-B,2026-10-21,25,24,1
"""
    # 1. All-or-nothing mode
    res_all = import_sessions_from_csv(repo, csv_text, allow_partial=False)
    assert res_all.imported_count == 0
    assert res_all.failed_count == 2  # line 2 (db collision) and line 3 (intra-file duplicate)
    # Verify stored record is NOT overwritten and no duplicate exists
    stored = repo.get_session_by_id(initial_session.session_id)
    assert stored.present_count == 29
    assert len(repo.get_sessions()) == 1

    # 2. Partial mode
    res_part = import_sessions_from_csv(repo, csv_text, allow_partial=True)
    assert res_part.imported_count == 1  # Only CLASS-02-B imported
    assert res_part.failed_count == 2
    # Verify stored record is STILL NOT overwritten
    stored_again = repo.get_session_by_id(initial_session.session_id)
    assert stored_again.present_count == 29
    # Total records is now 2 (original CLASS-01-A + new CLASS-02-B, no duplicates)
    all_sessions = repo.get_sessions()
    assert len(all_sessions) == 2
    assert {s.class_id for s in all_sessions} == {"CLASS-01-A", "CLASS-02-B"}


def test_preview_sessions_from_csv_does_not_write_to_database(repo):
    """Verify preview_sessions_from_csv validates and returns candidates without writing to DB."""
    csv_text = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
CLASS-02-B,2026-10-21,25,24,1
"""
    # 1. Preview valid CSV
    preview_res = preview_sessions_from_csv(repo, csv_text)
    assert preview_res.total_rows == 2
    assert preview_res.imported_count == 2
    assert preview_res.failed_count == 0
    assert len(preview_res.imported_sessions) == 2
    # Verify ZERO records written to database
    assert len(repo.get_sessions()) == 0

    # 2. Preview invalid CSV in all-or-nothing mode
    bad_csv = """class_id,session_date,expected_enrollment,present_count,absent_count
CLASS-01-A,2026-10-20,30,28,2
CLASS-02-B,2026-10-21,25,20,1
"""
    preview_bad = preview_sessions_from_csv(repo, bad_csv, allow_partial=False)
    assert preview_bad.total_rows == 2
    assert preview_bad.imported_count == 0
    assert preview_bad.failed_count == 1
    assert len(preview_bad.errors) == 1
    assert len(repo.get_sessions()) == 0


def test_sample_attendance_synthetic_csv_validity(repo):
    """Verify data/sample_attendance_synthetic.csv conforms to contract and imports cleanly."""
    sample_path = Path(__file__).resolve().parent.parent / "data" / "sample_attendance_synthetic.csv"
    assert sample_path.exists(), f"Sample CSV file not found at {sample_path}"

    with open(sample_path, "r", encoding="utf-8") as f:
        csv_text = f.read()

    # 1. Preview
    preview_res = preview_sessions_from_csv(repo, csv_text)
    assert preview_res.total_rows == 10
    assert preview_res.imported_count == 10
    assert preview_res.failed_count == 0
    assert len(preview_res.errors) == 0

    # 2. Import
    import_res = import_sessions_from_csv(repo, csv_text)
    assert import_res.imported_count == 10
    assert import_res.failed_count == 0
    assert len(repo.get_sessions()) == 10


def test_csv_import_utf8_bom_bytes(repo):
    """Verify that CSV input containing a UTF-8 BOM is decoded and imported cleanly."""
    raw_csv = (
        "\ufeffclass_id,session_date,expected_enrollment,present_count,absent_count\n"
        "CLASS-01-A,2026-10-25,30,28,2\n"
    )
    bytes_stream = io.BytesIO(raw_csv.encode("utf-8-sig"))

    res = import_sessions_from_csv(repo, bytes_stream)
    assert res.total_rows == 1
    assert res.imported_count == 1
    assert res.failed_count == 0
    assert len(repo.get_sessions()) == 1


def test_csv_import_crlf_line_endings(repo):
    """Verify that CSV input with Windows CRLF line endings is parsed without errors."""
    crlf_csv = (
        "class_id,session_date,expected_enrollment,present_count,absent_count\r\n"
        "CLASS-01-A,2026-10-25,30,28,2\r\n"
        "CLASS-02-B,2026-10-25,25,24,1\r\n"
    )
    res = import_sessions_from_csv(repo, crlf_csv)
    assert res.total_rows == 2
    assert res.imported_count == 2
    assert res.failed_count == 0
    assert len(repo.get_sessions()) == 2


def test_csv_import_unrecognized_columns_warning(repo):
    """Verify that unrecognized columns emit a descriptive warning while preserving valid data."""
    csv_text = (
        "class_id,session_date,expected_enrollment,present_count,absent_count,school_district,teacher_notes\n"
        "CLASS-01-A,2026-10-25,30,28,2,North-District,Nominal attendance\n"
    )
    res = import_sessions_from_csv(repo, csv_text)
    assert res.total_rows == 1
    assert res.imported_count == 1
    assert res.failed_count == 0
    assert len(res.warnings) == 1
    assert "unrecognized column(s)" in res.warnings[0]
    assert "school_district" in res.warnings[0]


def test_csv_import_blank_lines_skipped(repo):
    """Verify that blank lines at the beginning, middle, or end of a CSV are ignored."""
    csv_text = (
        "\n"
        "class_id,session_date,expected_enrollment,present_count,absent_count\n"
        "\n"
        "CLASS-01-A,2026-10-25,30,28,2\n"
        "   \n"
        "CLASS-02-B,2026-10-25,25,24,1\n"
        "\n"
    )
    res = import_sessions_from_csv(repo, csv_text)
    assert res.total_rows == 2
    assert res.imported_count == 2
    assert res.failed_count == 0
    assert len(repo.get_sessions()) == 2
