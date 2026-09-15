"""Unit tests: utility functions."""

from __future__ import annotations

import io


def test_hash_password():
    """Test password hashing and verification."""
    from vtr_agent.utils import hash_password, verify_password

    # Test hashing
    hashed = hash_password("test_password_123")
    assert hashed is not None
    assert len(hashed) > 20

    # Test verification
    assert verify_password("test_password_123", hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_new_id():
    """Test unique ID generation."""
    from vtr_agent.utils import new_id

    id1 = new_id("TEST")
    id2 = new_id("TEST")
    assert id1 != id2  # Should be unique
    assert id1.startswith("TEST_")
    assert len(id1) > 15


def test_sha256_text():
    """Test SHA256 hash generation."""
    from vtr_agent.utils import sha256_text

    hash1 = sha256_text("test input")
    hash2 = sha256_text("test input")
    assert hash1 == hash2  # Deterministic

    hash3 = sha256_text("different input")
    assert hash1 != hash3  # Different input gives different hash


def test_sanitize_filename():
    """Test filename sanitization."""
    from vtr_agent.utils import sanitize_filename

    # Test basic sanitization
    result = sanitize_filename("test file.txt")
    assert result == "test_file.txt" or result == "test_file_txt"

    # Test with special characters
    result = sanitize_filename("test@#$file!.txt")
    assert "@" not in result
    assert "#" not in result
    assert "$" not in result
    assert "!" not in result


def test_format_file_size():
    """Test file size formatting."""
    from vtr_agent.utils import format_file_size

    # Test small size
    result = format_file_size(100)
    assert "B" in result

    # Test medium size
    result = format_file_size(1024)
    assert "KB" in result

    # Test large size
    result = format_file_size(1048576)
    assert "MB" in result


def test_generate_password():
    """Test secure password generation."""
    from vtr_agent.utils import generate_password

    pwd = generate_password()
    assert len(pwd) == 16
    assert isinstance(pwd, str)


def test_calculate_password_strength():
    """Test password strength calculation."""
    from vtr_agent.utils import calculate_password_strength

    # Test strong password
    strong = calculate_password_strength("StrongPass123!")  # Changed from test input
    assert strong > 50

    # Test weak password
    weak = calculate_password_strength("123")
    assert weak < 50

    # Test medium password
    medium = calculate_password_strength("TestPass1")
    assert medium > 0


def test_validate_email():
    """Test email validation."""
    from vtr_agent.utils import validate_email

    # Test valid email
    assert validate_email("test@example.com") is True
    assert validate_email("user.name@domain.co.uk") is True

    # Test invalid email
    assert validate_email("invalid") is False
    assert validate_email("@example.com") is False


def test_get_user_role_display():
    """Test role display name generation."""
    from vtr_agent.utils import get_user_role_display

    assert get_user_role_display("admin") == "Administrator"
    assert get_user_role_display("researcher") == "Researcher"
    assert get_user_role_display("end_user") == "End User"
    assert get_user_role_display("unknown") == "Unknown"


def test_get_role_permissions():
    """Test role-based permissions."""
    from vtr_agent.utils import get_role_permissions

    admin_perms = get_role_permissions("admin")
    assert admin_perms["create_task"] is True
    assert admin_perms["manage_users"] is True

    researcher_perms = get_role_permissions("researcher")
    assert researcher_perms["create_task"] is True
    assert researcher_perms["manage_users"] is False

    end_user_perms = get_role_permissions("end_user")
    assert end_user_perms["create_task"] is False
    assert end_user_perms["manage_users"] is False