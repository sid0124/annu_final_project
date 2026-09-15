"""
VTR-Agent: User Utilities

Common utility functions for user management, ID generation, and security.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Dict, Optional

class RiskLevel(IntEnum):
    """Risk level classification for tasks and tool usage."""
    LEVEL_0 = 0  # Safe - automatic execution
    LEVEL_1 = 1  # Controlled - policy-supervised
    LEVEL_2 = 2  # High - requires human approval
    LEVEL_3 = 3  # Blocked - always prohibited

from passlib.context import CryptContext
from passlib.hash import pbkdf2_sha256

from vtr_agent.core.config import get_settings

# Password hashing context
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated=["auto"],
    pbkdf2_sha256__rounds=600000,
)

# Settings
settings = get_settings()


def hash_password(password: str) -> str:
    """Hash a password for storing.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a stored password against one provided by user.

    Args:
        plain_password: Plain text password
        hashed_password: Stored hashed password

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def login_ok(user: Any, password: str) -> bool:
    """Check if user exists and password is valid.

    Args:
        user: User model instance
        password: Plain text password

    Returns:
        True if user exists and password is valid
    """
    return user is not None and verify_password(password, user.password_hash)


def new_id(prefix: str) -> str:
    """Generate a new unique ID.

    Args:
        prefix: ID prefix (e.g., "USR", "PROJ", "DOC")

    Returns:
        Unique ID string
    """
    return f"{prefix}_{secrets.token_hex(8)}"


def sha256_text(text: str) -> str:
    """Generate SHA256 hash of text.

    Args:
        text: Text to hash

    Returns:
        SHA256 hash string
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utcnow_iso() -> str:
    """Get current UTC time in ISO format.

    Returns:
        ISO formatted timestamp string
    """
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%z")


def generate_username_from_email(email: str) -> str:
    """Generate username from email address.

    Args:
        email: User email address

    Returns:
        Generated username
    """
    base = email.split("@")[0]
    # Remove special characters and replace with underscore
    import re

    base = re.sub(r"[^a-zA-Z0-9_]", base, "")
    # Ensure uniqueness (in real implementation, check database)
    return base.lower()


def get_user_role_display(role: str) -> str:
    """Get display name for user role.

    Args:
        role: User role

    Returns:
        Display name for role
    """
    role_mapping = {
        "admin": "Administrator",
        "researcher": "Researcher",
        "reviewer": "Reviewer",
        "expert": "Domain Expert",
        "end_user": "End User",
    }
    return role_mapping.get(role, role.replace("_", " ").title())


def validate_email(email: str) -> bool:
    """Basic email validation.

    Args:
        email: Email address to validate

    Returns:
        True if email format is valid
    """
    import re

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    import re

    # Remove path components
    filename = filename.split("/")[-1].split("\\")[-1]
    # Remove special characters
    filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        filename = name[:255 - len(ext) - 1] + ("." + ext if ext else "")
    return filename


def get_file_extension(filename: str) -> str:
    """Get file extension from filename.

    Args:
        filename: Filename with extension

    Returns:
        File extension (without dot)
    """
    import re

    # Extract extension
    match = re.search(r"\.(.+)$", filename)
    return match.group(1).lower() if match else ""


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format.

    Args:
        size_bytes: File size in bytes

    Returns:
        Formatted file size
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def generate_password() -> str:
    """Generate a secure random password.

    Returns:
        Random password string
    """
    import random
    import string

    length = 16
    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    return "".join(random.choice(chars) for _ in range(length))


def calculate_password_strength(password: str) -> int:
    """Calculate password strength score (0-100).

    Args:
        password: Password to evaluate

    Returns:
        Strength score (0-100)
    """
    score = 0

    # Length
    score += min(len(password) * 2, 40)

    # Complexity
    if any(c.islower() for c in password):
        score += 15
    if any(c.isupper() for c in password):
        score += 15
    if any(c.isdigit() for c in password):
        score += 15
    if any(c in "!@#$%^&*()_+-=[]{}|;:',.<>?/" for c in password):
        score += 15

    # Entropy
    import math

    entropy = len(set(password)) * len(password) * math.log2(len(set(password))) if len(set(password)) > 1 else 0
    score += min(int(entropy / 2), 25)

    return min(score, 100)


def get_role_permissions(role: str) -> Dict[str, bool]:
    """Get permissions for a user role.

    Args:
        role: User role

    Returns:
        Dictionary of permissions
    """
    base_permissions = {
        "create_task": False,
        "upload_document": False,
        "request_tool": False,
        "approve_action": False,
        "review_evidence": False,
        "manage_users": False,
        "configure_tools": False,
        "view_audit_logs": False,
        "export_data": False,
    }

    role_permissions = {
        "admin": {
            **base_permissions,
            "create_task": True,
            "upload_document": True,
            "request_tool": True,
            "approve_action": True,
            "review_evidence": True,
            "manage_users": True,
            "configure_tools": True,
            "view_audit_logs": True,
            "export_data": True,
        },
        "researcher": {
            **base_permissions,
            "create_task": True,
            "upload_document": True,
            "request_tool": True,
            "approve_action": False,
            "review_evidence": True,
            "manage_users": False,
            "configure_tools": False,
            "view_audit_logs": True,
            "export_data": False,
        },
        "reviewer": {
            **base_permissions,
            "create_task": False,
            "upload_document": False,
            "request_tool": False,
            "approve_action": True,
            "review_evidence": True,
            "manage_users": False,
            "configure_tools": False,
            "view_audit_logs": True,
            "export_data": False,
        },
        "expert": {
            **base_permissions,
            "create_task": False,
            "upload_document": False,
            "request_tool": True,
            "approve_action": False,
            "review_evidence": True,
            "manage_users": False,
            "configure_tools": False,
            "view_audit_logs": True,
            "export_data": False,
        },
        "end_user": {
            **base_permissions,
            "create_task": False,
            "upload_document": False,
            "request_tool": False,
            "approve_action": False,
            "review_evidence": False,
            "manage_users": False,
            "configure_tools": False,
            "view_audit_logs": False,
            "export_data": False,
        },
    }

    return role_permissions.get(role, base_permissions)
