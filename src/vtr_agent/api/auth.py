"""
VTR-Agent: Auth API

Authentication API endpoints for user login, logout, and token management.
"""
from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from vtr_agent.api.schemas import LoginRequest, LoginResponse
from vtr_agent.auth.security import (
    create_access_token,
    decode_token,
    get_current_user,
    verify_password,
)
from vtr_agent.core.database import models as m
from vtr_agent.core.database.session import get_db
from vtr_agent.utils import new_id

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate with username or email + password."""
    user = (
        db.query(m.User)
        .filter((m.User.username == body.username) | (m.User.email == body.username))
        .first()
    )

    password = body.password.get_secret_value()
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=401, detail="Invalid username or password."
        )

    token = create_access_token(
        {"sub": user.user_id, "role": user.role, "username": user.username}
    )
    user.last_login_at = new_id("TS")
    db.commit()

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=3600,
        user={
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "is_demo": user.is_demo,
        },
    )


@router.post("/logout")
def logout(
    request: Request, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)
):
    """Logout the current user."""
    return {"ok": True, "message": "Logged out."}



@router.get("/me", response_model=Dict)
def me(user: m.User = Depends(get_current_user)):
    """Get current user information."""
    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "is_demo": user.is_demo,
        "last_login_at": user.last_login_at,
    }



@router.post("/refresh")
def refresh_token(request: Request, db: Session = Depends(get_db)):
    """Refresh access token."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")

    token = auth_header.split(" ")[1]
    try:
        payload = decode_token(token)
        user = db.query(m.User).filter(m.User.user_id == payload["sub"]).first()

        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")

        new_token = create_access_token(
            {"sub": user.user_id, "role": user.role, "username": user.username}
        )

        return {
            "access_token": new_token,
            "token_type": "bearer",
            "expires_in": 3600,
        }

    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e
