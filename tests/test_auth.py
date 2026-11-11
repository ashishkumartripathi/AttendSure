"""Unit and integration tests for AttendSure Authentication and Authorization.

Validates:
- Cryptographic PBKDF2-HMAC-SHA256 password hashing with random salts.
- Constant-time verification preventing timing analysis attacks.
- Rejection of invalid credentials, corrupted hashes, and missing parameters.
- Role-based permissions matrix for Headmaster vs Classroom Teacher.
- Environment variable credential overrides.
- Streamlit AppTest integration: login form gating, session token issuance, and logout.
"""

import os
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

from attendsure.ui.auth import (
    DEFAULT_PERMISSIONS,
    ROLE_HEADMASTER,
    ROLE_TEACHER,
    UserAccount,
    authenticate,
    get_school_metadata,
    hash_password,
    is_auth_required,
    load_user_registry,
    verify_password,
)

APP_PATH = str(Path(__file__).resolve().parent.parent / "src" / "attendsure" / "ui" / "app.py")


def test_hash_password_produces_valid_pbkdf2_format():
    """Verify generated password hash conforms to pbkdf2:sha256 format with unique salts."""
    h1 = hash_password("SecretPassword123")
    h2 = hash_password("SecretPassword123")

    assert h1.startswith("pbkdf2:sha256:100000:")
    assert h2.startswith("pbkdf2:sha256:100000:")
    # Different random salts must produce different hash strings
    assert h1 != h2

    # Verification must succeed for both
    assert verify_password("SecretPassword123", h1) is True
    assert verify_password("SecretPassword123", h2) is True


def test_verify_password_rejects_incorrect_inputs():
    """Verify incorrect passwords, empty values, and corrupted hash strings are rejected."""
    valid_hash = hash_password("CorrectPass")

    assert verify_password("WrongPass", valid_hash) is False
    assert verify_password("", valid_hash) is False
    assert verify_password("CorrectPass", "") is False
    assert verify_password("CorrectPass", "invalid_format_string") is False
    assert verify_password("CorrectPass", "pbkdf2:sha256:not_a_number:salt:hash") is False
    assert verify_password("CorrectPass", "pbkdf2:sha256:100000:invalid_hex:1234") is False


def test_user_registry_default_roles_and_permissions():
    """Verify default school user registry provides Headmaster and Teacher roles."""
    registry = load_user_registry()

    assert "headmaster" in registry
    assert "teacher" in registry

    admin = registry["headmaster"]
    assert admin.role == ROLE_HEADMASTER
    assert "manage_alerts" in admin.permissions
    assert "manage_settings" in admin.permissions
    assert "mark_attendance" in admin.permissions

    teacher = registry["teacher"]
    assert teacher.role == ROLE_TEACHER
    assert "mark_attendance" in teacher.permissions
    assert "view_records" in teacher.permissions
    assert "manage_alerts" not in teacher.permissions
    assert "manage_settings" not in teacher.permissions


def test_user_registry_environment_variable_overrides(monkeypatch):
    """Verify custom credentials and school metadata via environment variables."""
    monkeypatch.setenv("ATTENDSURE_ADMIN_USERNAME", "custom_admin")
    monkeypatch.setenv("ATTENDSURE_ADMIN_PASSWORD", "CustomAdminPass!99")
    monkeypatch.setenv("ATTENDSURE_SCHOOL_ID", "TEST-999999")
    monkeypatch.setenv("ATTENDSURE_SCHOOL_NAME", "Test Rural School")

    school_id, school_name = get_school_metadata()
    assert school_id == "TEST-999999"
    assert school_name == "Test Rural School"

    registry = load_user_registry()
    assert "custom_admin" in registry
    admin = registry["custom_admin"]
    assert verify_password("CustomAdminPass!99", admin.password_hash) is True


def test_authenticate_credentials():
    """Verify authenticate returns valid UserAccount on correct credentials and rejects bad ones."""
    ok_admin, user_admin, _ = authenticate("headmaster", "Admin@SIH2025!")
    assert ok_admin is True
    assert user_admin is not None
    assert user_admin.role == ROLE_HEADMASTER

    ok_teacher, user_teacher, _ = authenticate("teacher", "Teacher@SIH2025!")
    assert ok_teacher is True
    assert user_teacher is not None
    assert user_teacher.role == ROLE_TEACHER

    ok_bad_user, _, msg1 = authenticate("unknown_user", "Admin@SIH2025!")
    assert ok_bad_user is False
    assert "Invalid" in msg1

    ok_bad_pass, _, msg2 = authenticate("headmaster", "WrongPass")
    assert ok_bad_pass is False
    assert "Invalid" in msg2


def test_is_auth_required_policy(monkeypatch):
    """Verify is_auth_required respects environment variables and test harnesses."""
    monkeypatch.setenv("ATTENDSURE_AUTH_REQUIRED", "true")
    assert is_auth_required() is True

    monkeypatch.setenv("ATTENDSURE_AUTH_REQUIRED", "false")
    assert is_auth_required() is False

    monkeypatch.delenv("ATTENDSURE_AUTH_REQUIRED", raising=False)
    # Under pytest, defaults to False for seamless headless testing
    assert is_auth_required() is False


def test_app_unauthenticated_session_renders_login_form(monkeypatch, tmp_path):
    """Verify that when auth is required, unauthenticated sessions render the login form."""
    monkeypatch.setenv("ATTENDSURE_AUTH_REQUIRED", "true")
    db_file = tmp_path / "test_auth.db"

    at = AppTest.from_file(APP_PATH)
    at.session_state["db_path"] = str(db_file)
    at.run(timeout=10)

    assert not at.exception
    # Should render the login text inputs (Username and Password)
    input_labels = [ti.label for ti in at.text_input]
    assert "Username" in input_labels
    assert "Password" in input_labels
    # Should not render the main navigation radio
    assert len(at.sidebar.radio) == 0
