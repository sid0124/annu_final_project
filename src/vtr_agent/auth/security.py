"""
VTR-Agent: Authentication Security

JWT token generation, validation, and security utilities.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import HTTPException, status
from jose import JWTError, jwt

from vtr_agent.core.config import get_settings

# Settings
settings = get_settings()

# JWT configuration
JWT_SECRET = settings.JWT_SECRET_KEY
JWT_ALGORITHM = settings.JWT_ALGORITHM
JWT_ACCESS_TOKEN_EXPIRES = settings.JWT_ACCESS_TOKEN_EXPIRES

# Password hashing
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated=["auto"],
    pbkdf2_sha256__rounds=600000,
)


def create_access_token(data: Dict[str, Any], expires_delta: int | None = None) -> str:
    """Create JWT access token.

    Args:
        data: Token data (user_id, role, etc.)
        expires_delta: Token expiration in seconds

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta is None:
        expires_delta = JWT_ACCESS_TOKEN_EXPIRES

    expire = datetime.now(timezone.utc) + timedelta(seconds=expires_delta)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """Decode JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token data

    Raises:
        HTTPException: If token is invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from e


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create JWT refresh token.

    Args:
        data: Token data

    Returns:
        Encoded refresh token
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def validate_token(token: str) -> Dict[str, Any]:
    """Validate JWT token and return payload.

    Args:
        token: JWT token string

    Returns:
        Validated token payload

    Raises:
        HTTPException: If token validation fails
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        # Check expiration
        exp = payload.get("exp")
        if exp is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing expiration",
            )

        if datetime.now(timezone.utc).timestamp() > exp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            )

        return payload

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from e


def generate_token_pair(user_id: str, role: str) -> Dict[str, str]:
    """Generate access and refresh token pair.

    Args:
        user_id: User identifier
        role: User role

    Returns:
        Dictionary with access_token and refresh_token
    """
    access_token_data = {"sub": user_id, "role": role, "token_type": "access"}
    refresh_token_data = {
        "sub": user_id,
        "role": role,
        "token_type": "refresh",
        "jti": f"{user_id}_{int(time.time())}",
    }

    access_token = create_access_token(access_token_data)
    refresh_token = create_refresh_token(refresh_token_data)

    return {"access_token": access_token, "refresh_token": refresh_token}


def extract_user_id_from_token(token: str) -> str:
    """Extract user ID from JWT token.

    Args:
        token: JWT token string

    Returns:
        User ID
    """
    payload = decode_token(token)
    return payload.get("sub", "")


def extract_role_from_token(token: str) -> str:
    """Extract role from JWT token.

    Args:
        token: JWT token string

    Returns:
        User role
    """
    payload = decode_token(token)
    return payload.get("role", "")


def is_token_valid(token: str) -> bool:
    """Check if token is valid.

    Args:
        token: JWT token string

    Returns:
        True if token is valid, False otherwise
    """
    try:
        decode_token(token)
        return True
    except HTTPException:
        return False


def rotate_token(old_token: str) -> str:
    """Rotate token to new token.

    Args:
        old_token: Old JWT token

    Returns:
        New JWT token
    """
    payload = decode_token(old_token)
    return create_access_token(payload)


def revoke_token(token: str) -> bool:
    """Revoke token (invalidation).

    Args:
        token: JWT token to revoke

    Returns:
        True if token was revoked, False otherwise
    """
    # Implementation depends on your token storage mechanism
    # For JWT, this is typically handled client-side
    return True


def get_token_expiry(token: str) -> datetime:
    """Get token expiration time.

    Args:
        token: JWT token string

    Returns:
        Token expiration datetime
    """
    payload = decode_token(token)
    exp = payload.get("exp")
    if exp:
        return datetime.fromtimestamp(exp, tz=timezone.utc)
    return datetime.now(timezone.utc)


def is_token_expired(token: str) -> bool:
    """Check if token is expired.

    Args:
        token: JWT token string

    Returns:
        True if token is expired, False otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        exp = payload.get("exp")
        if exp is None:
            return True
        return datetime.now(timezone.utc).timestamp() > exp
    except JWTError:
        return True


def validate_token_claims(token: str, expected_claims: Dict[str, Any]) -> bool:
    """Validate token claims against expected values.

    Args:
        token: JWT token string
        expected_claims: Expected token claims

    Returns:
        True if claims match, False otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        for key, value in expected_claims.items():
            if payload.get(key) != value:
                return False

        return True
    except JWTError:
        return False


def create_token_with_custom_expiry(
    data: Dict[str, Any], expires_minutes: int
) -> str:
    """Create JWT token with custom expiration.

    Args:
        data: Token data
        expires_minutes: Token expiration in minutes

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


# ---------------------------------------------------------------------------
# FastAPI Dependencies
# ---------------------------------------------------------------------------

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

_bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
):
    """FastAPI dependency — decode Bearer token and return the current User model.

    Opens its own DB session so callers just write::

        user: m.User = Depends(get_current_user)

    In tests, override ``vtr_agent.core.database.session.get_db`` (or
    ``vtr_agent.auth.security._get_db_for_auth``) via
    ``app.dependency_overrides`` to supply the test DB session.
    """
    from vtr_agent.core.database import models as m

    payload = decode_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing 'sub'",
        )

    # Late-import to allow override_get_db in conftest to take effect.
    from vtr_agent.core.database.session import SessionLocal
    db = SessionLocal()
    try:
        user = db.query(m.User).filter(m.User.user_id == user_id).first()
    finally:
        db.close()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def require_role(*allowed_roles: str):
    """Factory that returns a FastAPI dependency enforcing role-based access.

    Usage::

        @router.post("/admin-only")
        def admin_action(user = Depends(require_role("admin"))):
            ...
    """
    def _dependency(
        credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
        db: Session = Depends(lambda: None),  # will be overridden at route level
    ):
        payload = decode_token(credentials.credentials)
        role = payload.get("role", "")
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' is not permitted for this operation.",
            )
        return payload

    return _dependency
