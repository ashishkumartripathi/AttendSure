"""Tests for AttendSure Demonstration Database Seeder and Safety Guards."""

from datetime import datetime
from pathlib import Path
import sqlite3
import pytest

from attendsure.data.demo_seed import prepare_demo_database, main
from attendsure.data.storage import DEFAULT_DB_PATH, AttendanceRepository


class TestDemoDatabaseSafetyGuards:
    """Verifies that the demonstration database preparation workflow enforces strict safety."""

    def test_rejects_operational_database_path(self):
        """Must reject targeting the canonical operational database."""
        with pytest.raises(ValueError, match="Safety Guard Violation.*active operational database"):
            prepare_demo_database(dest_path=DEFAULT_DB_PATH)

    def test_rejects_relative_operational_path(self):
        """Must reject relative references that resolve to the operational database."""
        rel_path = Path("data/attendsure.db")
        with pytest.raises(ValueError, match="Safety Guard Violation.*active operational database"):
            prepare_demo_database(dest_path=rel_path)

    def test_rejects_existing_file(self, tmp_path):
        """Must reject overwriting an already existing database file."""
        existing_file = tmp_path / "already_exists.db"
        existing_file.write_text("dummy")

        with pytest.raises(FileExistsError, match="Safety Guard Violation.*already exists"):
            prepare_demo_database(dest_path=existing_file)

    def test_rejects_empty_or_whitespace_path(self):
        """Must reject empty, None, or whitespace paths."""
        with pytest.raises(ValueError, match="Destination database path must be explicitly provided"):
            prepare_demo_database(dest_path="")

        with pytest.raises(ValueError, match="Destination database path must be explicitly provided"):
            prepare_demo_database(dest_path="   ")


class TestDemoDatabaseGeneration:
    """Verifies generation, schema conformance, and scenario invariants."""

    def test_successful_demo_database_generation(self, tmp_path):
        """Generates a fully populated demonstration database with sessions and alerts."""
        demo_db = tmp_path / "demo_test.db"

        result = prepare_demo_database(dest_path=demo_db, random_seed=42, run_detection=True)

        assert result["status"] == "success"
        assert result["database_path"] == str(demo_db.resolve())
        assert result["total_sessions"] == 60  # 5 cohorts * 12 sessions
        assert len(result["cohorts"]) == 5
        assert result["total_alerts"] >= 4

        # Verify repository inspection
        repo = AttendanceRepository(db_path=demo_db)
        try:
            sessions = repo.get_sessions()
            alerts = repo.get_alerts()

            assert len(sessions) == 60
            assert len(alerts) == result["total_alerts"]

            # Invariant checks across all sessions
            for s in sessions:
                assert s.present_count + s.absent_count == s.expected_enrollment
                assert s.record_source == "SYNTHETIC"
                assert s.expected_enrollment > 0
                assert s.present_count >= 0
                assert s.absent_count >= 0
                # Date format check
                datetime.fromisoformat(s.session_date)

            # Scenario 1: CLASS-01-A has 0 alerts
            class_1_alerts = [a for a in alerts if a.class_id == "CLASS-01-A"]
            assert len(class_1_alerts) == 0

            # Scenario 2: CLASS-02-B has attendance drop alert
            class_2_alerts = [a for a in alerts if a.class_id == "CLASS-02-B"]
            assert any(a.rule_id == "RULE_ATTENDANCE_DROP" for a in class_2_alerts)

            # Scenario 3: CLASS-03-C has repeated headcount alert
            class_3_alerts = [a for a in alerts if a.class_id == "CLASS-03-C"]
            assert any(a.rule_id == "RULE_REPEATED_HEADCOUNT" for a in class_3_alerts)

            # Scenario 4: CLASS-04-D has simulated camera discrepancy alert
            class_4_alerts = [a for a in alerts if a.class_id == "CLASS-04-D"]
            assert any(a.rule_id == "RULE_WEBCAM_DISCREPANCY" for a in class_4_alerts)

            # Scenario 5: CLASS-05-E has mixture of alerts
            class_5_alerts = [a for a in alerts if a.class_id == "CLASS-05-E"]
            assert len(class_5_alerts) >= 1

        finally:
            repo.close()

    def test_demo_database_generation_without_detection(self, tmp_path):
        """Generates a demo database with sessions only when run_detection=False."""
        demo_db = tmp_path / "demo_no_detect.db"

        result = prepare_demo_database(dest_path=demo_db, random_seed=42, run_detection=False)

        assert result["status"] == "success"
        assert result["total_sessions"] == 60
        assert result["total_alerts"] == 0

        repo = AttendanceRepository(db_path=demo_db)
        try:
            assert len(repo.get_sessions()) == 60
            assert len(repo.get_alerts()) == 0
        finally:
            repo.close()

    def test_deterministic_seed_reproducibility(self, tmp_path):
        """Two generations with the same seed yield identical sessions and alerts."""
        db1 = tmp_path / "demo_seed_a.db"
        db2 = tmp_path / "demo_seed_b.db"

        res1 = prepare_demo_database(dest_path=db1, random_seed=12345, run_detection=True)
        res2 = prepare_demo_database(dest_path=db2, random_seed=12345, run_detection=True)

        assert res1["total_sessions"] == res2["total_sessions"]
        assert res1["total_alerts"] == res2["total_alerts"]
        assert res1["alerts_by_rule"] == res2["alerts_by_rule"]

        repo1 = AttendanceRepository(db_path=db1)
        repo2 = AttendanceRepository(db_path=db2)
        try:
            s1 = repo1.get_sessions()
            s2 = repo2.get_sessions()
            assert len(s1) == len(s2)
            for a, b in zip(s1, s2):
                assert a.class_id == b.class_id
                assert a.session_date == b.session_date
                assert a.present_count == b.present_count
                assert a.absent_count == b.absent_count
                assert a.webcam_count == b.webcam_count
        finally:
            repo1.close()
            repo2.close()


class TestDemoCLI:
    """Verifies CLI entrypoint behavior and argument parsing."""

    def test_cli_execution_success(self, tmp_path, monkeypatch, capsys):
        """Tests CLI main with valid destination."""
        dest_db = tmp_path / "cli_demo.db"
        monkeypatch.setattr(
            "sys.argv",
            ["prepare_demo_database.py", "--dest", str(dest_db), "--seed", "42"],
        )

        main()
        captured = capsys.readouterr()
        assert "AttendSure Demonstration Database Ready" in captured.out
        assert str(dest_db.resolve()) in captured.out
        assert dest_db.exists()

    def test_cli_execution_failure_on_existing_file(self, tmp_path, monkeypatch, capsys):
        """Tests CLI main exits with code 1 if file already exists."""
        existing = tmp_path / "existing.db"
        existing.write_text("data")
        monkeypatch.setattr(
            "sys.argv",
            ["prepare_demo_database.py", "--dest", str(existing)],
        )

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error preparing demonstration database" in captured.out
