import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account_deletion import delete_user_account
from app.auth_security import check_login_allowed, clear_login_lockout, record_failed_login
from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserRole, Vehicle
from app.recaptcha import verify_recaptcha
from app.recovery_security import (
    GENERIC_RECOVERY_ERROR,
    check_recovery_allowed,
    clear_recovery_lockout,
    log_recovery_event,
    record_failed_recovery,
)
from app.schemas import (
    AccountDeleteIn,
    DriverRegister,
    PassengerRegister,
    PasswordRecoveryResetIn,
    PasswordRecoveryResetOut,
    PasswordRecoveryVerifyIn,
    PasswordRecoveryVerifyOut,
    TokenResponse,
    UserLogin,
    UserPublic,
    UserRegister,
    utc_now,
)
from app.rate_limit import limiter
from app.security import (
    create_access_token,
    create_password_reset_token,
    decode_password_reset_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_LOGIN_ERROR = "Correo o contraseña incorrectos."
EMAIL_ALREADY_REGISTERED = (
    "Este correo ya tiene una cuenta. Inicia sesión o elimínala para volver a registrarla."
)


def _split_full_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(None, 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _check_captcha(token: str | None, action: str) -> None:
    try:
        verify_recaptcha(token, action)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _ensure_email_available(db: Session, email: str) -> None:
    exists = db.execute(select(User.id).where(User.email == email)).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EMAIL_ALREADY_REGISTERED)


@router.post("/register", response_model=UserPublic)
@limiter.limit("8/minute")
def register(request: Request, body: UserRegister, db: Session = Depends(get_db)) -> User:
    _check_captcha(body.captcha_token, "register")
    email = str(body.email).lower().strip()
    _ensure_email_available(db, email)

    fn, ln = _split_full_name(body.full_name)
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        first_name=fn,
        last_name=ln,
        phone=None,
        espol_verified_at=None,
        role=body.role,
        created_at=utc_now(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/passenger/register", response_model=UserPublic)
@limiter.limit("8/minute")
def passenger_register(
    request: Request, body: PassengerRegister, db: Session = Depends(get_db)
) -> User:
    _check_captcha(body.captcha_token, "passenger_register")
    email = str(body.email).lower().strip()
    _ensure_email_available(db, email)

    now = utc_now()
    first = body.first_name.strip()
    last = body.last_name.strip()
    full_name = f"{first} {last}".strip()

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        recovery_phrase_hash=hash_password(body.recovery_phrase),
        full_name=full_name,
        first_name=first,
        last_name=last,
        phone=body.phone.strip(),
        espol_verified_at=now,
        role=UserRole.student,
        created_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/driver/register", response_model=UserPublic)
@limiter.limit("8/minute")
def driver_register(request: Request, body: DriverRegister, db: Session = Depends(get_db)) -> User:
    _check_captcha(body.captcha_token, "driver_register")
    email = str(body.email).lower().strip()
    _ensure_email_available(db, email)

    now = utc_now()
    first = body.first_name.strip()
    last = body.last_name.strip()
    full_name = f"{first} {last}".strip()

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        recovery_phrase_hash=hash_password(body.recovery_phrase),
        full_name=full_name,
        first_name=first,
        last_name=last,
        phone=body.phone.strip(),
        espol_verified_at=None,
        role=UserRole.driver,
        created_at=now,
    )
    db.add(user)
    db.flush()

    vehicle = Vehicle(
        owner_id=user.id,
        plate=body.plate.strip(),
        brand=body.brand.strip(),
        model=body.model.strip(),
        created_at=now,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("12/minute")
def login(request: Request, body: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    _check_captcha(body.captcha_token, "login")
    email = str(body.email).lower().strip()
    check_login_allowed(db, email)

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        record_failed_login(db, email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    clear_login_lockout(db, email)
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
def delete_my_account(
    request: Request,
    body: AccountDeleteIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contraseña incorrecta. No se eliminó la cuenta.",
        )
    delete_user_account(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password-recovery/verify", response_model=PasswordRecoveryVerifyOut)
@limiter.limit("8/minute")
def password_recovery_verify(
    request: Request,
    body: PasswordRecoveryVerifyIn,
    db: Session = Depends(get_db),
) -> PasswordRecoveryVerifyOut:
    _check_captcha(body.captcha_token, "password_recovery_verify")
    email = str(body.email).lower().strip()
    check_recovery_allowed(db, email)

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if (
        user is None
        or not user.recovery_phrase_hash
        or not verify_password(body.recovery_phrase, user.recovery_phrase_hash)
    ):
        record_failed_recovery(db, email, request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_RECOVERY_ERROR)

    clear_recovery_lockout(db, email, request)
    reset_token = create_password_reset_token(str(user.id))
    return PasswordRecoveryVerifyOut(
        reset_token=reset_token,
        expires_in_minutes=settings.password_reset_token_minutes,
    )


@router.post("/password-recovery/reset", response_model=PasswordRecoveryResetOut)
@limiter.limit("8/minute")
def password_recovery_reset(
    request: Request,
    body: PasswordRecoveryResetIn,
    db: Session = Depends(get_db),
) -> PasswordRecoveryResetOut:
    user_id = decode_password_reset_token(body.reset_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de recuperación expiró o no es válido. Vuelve a verificar tu palabra clave.",
        )

    from uuid import UUID

    try:
        uid = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido.") from exc

    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido.")

    user.password_hash = hash_password(body.new_password)
    clear_login_lockout(db, user.email)
    log_recovery_event(db, user.email, "reset_ok", request)
    db.commit()
    return PasswordRecoveryResetOut()
