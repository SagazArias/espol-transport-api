import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import PasswordRecoveryLockout, PasswordRecoveryLog

logger = logging.getLogger(__name__)

GENERIC_RECOVERY_ERROR = "Correo o palabra clave incorrectos."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client:
        return request.client.host[:64]
    return None


def log_recovery_event(
    db: Session,
    email: str,
    event_type: str,
    request: Request | None = None,
) -> None:
    row = PasswordRecoveryLog(
        email=email.lower(),
        event_type=event_type,
        ip_address=_client_ip(request),
        created_at=_now(),
    )
    db.add(row)
    logger.info(
        "password_recovery email=%s event=%s ip=%s",
        email.lower(),
        event_type,
        _client_ip(request),
    )


def check_recovery_allowed(db: Session, email: str) -> None:
    row = db.get(PasswordRecoveryLockout, email.lower())
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
        detail=f"Demasiados intentos. Espera {remaining} minuto(s) antes de volver a intentar.",
    )


def record_failed_recovery(db: Session, email: str, request: Request | None = None) -> None:
    key = email.lower()
    now = _now()
    row = db.get(PasswordRecoveryLockout, key)
    if row is None:
        row = PasswordRecoveryLockout(email=key, failed_attempts=0, locked_until=None, updated_at=now)
        db.add(row)
    row.failed_attempts += 1
    row.updated_at = now
    if row.failed_attempts >= settings.recovery_max_failed_attempts:
        row.locked_until = now + timedelta(minutes=settings.recovery_lockout_minutes)
        log_recovery_event(db, key, "locked", request)
    log_recovery_event(db, key, "verify_failed", request)
    db.commit()


def clear_recovery_lockout(db: Session, email: str, request: Request | None = None) -> None:
    row = db.get(PasswordRecoveryLockout, email.lower())
    if row is None:
        log_recovery_event(db, email, "verify_ok", request)
        db.commit()
        return
    row.failed_attempts = 0
    row.locked_until = None
    row.updated_at = _now()
    log_recovery_event(db, email, "verify_ok", request)
    db.commit()
