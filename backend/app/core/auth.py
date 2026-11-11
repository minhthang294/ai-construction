"""Server-side bearer sessions; no seeded credentials."""

import contextvars
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select

from .database import SessionLocal
from .models import ApiToken, User

_user: contextvars.ContextVar[User | None] = contextvars.ContextVar("request_user", default=None)


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"{salt.hex()}:{digest.hex()}"


def password_valid(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split(":", 1)
        actual = password_hash(password, bytes.fromhex(salt)).split(":", 1)[1]
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def issue_token(user: User) -> str:
    token = secrets.token_urlsafe(32)
    with SessionLocal() as db:
        db.add(ApiToken(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
                        expires_at=datetime.now(timezone.utc) + timedelta(hours=12)))
        db.commit()
    return token


def authenticate(token: str) -> User:
    digest = hashlib.sha256(token.encode()).hexdigest()
    with SessionLocal() as db:
        row = db.scalar(select(ApiToken).where(ApiToken.token_hash == digest))
        if row is None or row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(401, "Invalid or expired token")
        user = db.get(User, row.user_id)
        if user is None:
            raise HTTPException(401, "Invalid token")
        db.expunge(user)
        return user


def set_current_user(user: User | None):
    return _user.set(user)


def reset_current_user(token):
    _user.reset(token)


def get_current_user() -> User:
    user = _user.get()
    if user is None:
        raise HTTPException(401, "Authentication required")
    return user
