from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import LoginLockout


def _now() -> datetime:
    return datetime.now(timezone.utc)


def check_login_allowed(db: Session, email: str) -> None:
    row = db.get(LoginLockout, email.lower())
    if row is None or row.locked_until is None:
        return
    if row.locked_until <= _now():
        row.failed_attempts = 0
        row.locked_until = None
        row.updated_at = _now()
        db.commit()
        return
    remaining = int((row.locked_until - _now()).total_seconds() // 60) + 1
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Cuenta bloqueada temporalmente por intentos fallidos. Intenta en {remaining} minuto(s).",
    )


def record_failed_login(db: Session, email: str) -> None:
    key = email.lower()
    now = _now()
    row = db.get(LoginLockout, key)
    if row is None:
        row = LoginLockout(email=key, failed_attempts=0, locked_until=None, updated_at=now)
        db.add(row)
    row.failed_attempts += 1
    row.updated_at = now
    if row.failed_attempts >= settings.login_max_failed_attempts:
        row.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
    db.commit()


def clear_login_lockout(db: Session, email: str) -> None:
    row = db.get(LoginLockout, email.lower())
    if row is None:
        return
    row.failed_attempts = 0
    row.locked_until = None
    row.updated_at = _now()
    db.commit()
