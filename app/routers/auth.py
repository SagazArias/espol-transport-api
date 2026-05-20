import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_security import check_login_allowed, clear_login_lockout, record_failed_login
from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.email_service import EmailDeliveryError, send_student_verification_email
from app.models import StudentEmailOtp, User, UserRole, Vehicle
from app.otp_utils import generate_six_digit_code, hash_otp, verify_otp
from app.recaptcha import verify_recaptcha
from app.recovery_security import (
    GENERIC_RECOVERY_ERROR,
    check_recovery_allowed,
    clear_recovery_lockout,
    log_recovery_event,
    record_failed_recovery,
)
from app.schemas import (
    DriverRegister,
    OtpSentResponse,
    PassengerRegister,
    PassengerSendOtp,
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
GENERIC_REGISTER_ERROR = "No se pudo completar el registro. Verifica los datos e inténtalo de nuevo."
GENERIC_OTP_SENT = (
    "Si el correo es institucional (@espol.edu.ec) y no está registrado, "
    "recibirás un código de 6 dígitos en los próximos minutos."
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


@router.post("/register", response_model=UserPublic)
@limiter.limit("8/minute")
def register(request: Request, body: UserRegister, db: Session = Depends(get_db)) -> User:
    _check_captcha(body.captcha_token, "register")
    exists = db.execute(select(User.id).where(User.email == str(body.email).lower())).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=GENERIC_REGISTER_ERROR)

    fn, ln = _split_full_name(body.full_name)
    user = User(
        email=str(body.email).lower(),
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


@router.post("/passenger/send-otp", response_model=OtpSentResponse)
@limiter.limit("5/minute")
def passenger_send_otp(
    request: Request, body: PassengerSendOtp, db: Session = Depends(get_db)
) -> OtpSentResponse:
    _check_captcha(body.captcha_token, "passenger_send_otp")
    email = str(body.email).lower().strip()

    exists = db.execute(select(User.id).where(User.email == email)).scalar_one_or_none()
    if exists is not None:
        return OtpSentResponse(
            message=GENERIC_OTP_SENT,
            expires_in_minutes=settings.student_otp_ttl_minutes,
            dev_code=None,
        )

    now = utc_now()
    latest = db.execute(
        select(StudentEmailOtp)
        .where(StudentEmailOtp.email == email)
        .order_by(StudentEmailOtp.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest is not None and (now - latest.created_at).total_seconds() < settings.student_otp_resend_seconds:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Espera {settings.student_otp_resend_seconds} segundos antes de pedir otro código.",
        )

    code = generate_six_digit_code()
    expires = now + timedelta(minutes=settings.student_otp_ttl_minutes)
    row = StudentEmailOtp(
        email=email,
        code_hash=hash_otp(email, code),
        expires_at=expires,
        consumed_at=None,
        created_at=now,
    )
    db.add(row)
    db.flush()
    try:
        send_student_verification_email(email, code)
    except EmailDeliveryError as exc:
        db.rollback()
        logger.error(
            "OTP email failed for %s: %s",
            email,
            exc,
            exc_info=exc.cause or exc,
        )
        detail = "No se pudo enviar el correo de verificación. Contacta al administrador."
        if settings.expose_api_errors:
            detail = f"{detail} ({exc})"
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from exc
    db.commit()

    dev_code = code if settings.expose_dev_otp else None
    return OtpSentResponse(
        message=GENERIC_OTP_SENT,
        expires_in_minutes=settings.student_otp_ttl_minutes,
        dev_code=dev_code,
    )


@router.post("/passenger/register", response_model=UserPublic)
@limiter.limit("8/minute")
def passenger_register(
    request: Request, body: PassengerRegister, db: Session = Depends(get_db)
) -> User:
    _check_captcha(body.captcha_token, "passenger_register")
    email = str(body.email).lower().strip()

    exists = db.execute(select(User.id).where(User.email == email)).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=GENERIC_REGISTER_ERROR)

    now = utc_now()
    challenge = db.execute(
        select(StudentEmailOtp)
        .where(
            StudentEmailOtp.email == email,
            StudentEmailOtp.consumed_at.is_(None),
            StudentEmailOtp.expires_at > now,
        )
        .order_by(StudentEmailOtp.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if challenge is None or not verify_otp(email, body.otp_code, challenge.code_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código inválido o expirado. Solicita un nuevo código.",
        )

    challenge.consumed_at = now

    full_name = f"{body.first_name.strip()} {body.last_name.strip()}".strip()
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        recovery_phrase_hash=hash_password(body.recovery_phrase),
        full_name=full_name,
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
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

    exists = db.execute(select(User.id).where(User.email == email)).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=GENERIC_REGISTER_ERROR)

    now = utc_now()
    full_name = f"{body.first_name.strip()} {body.last_name.strip()}".strip()
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        recovery_phrase_hash=hash_password(body.recovery_phrase),
        full_name=full_name,
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
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
