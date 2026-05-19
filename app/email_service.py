import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """SMTP send failed."""


def send_student_verification_email(to_email: str, code: str) -> None:
    subject = "Código de verificación — ESPOL Transporte"
    body = (
        f"Hola,\n\n"
        f"Tu código de verificación para ESPOL Transporte es: {code}\n\n"
        f"Caduca en {settings.student_otp_ttl_minutes} minutos.\n\n"
        f"Si no solicitaste este código, ignora este mensaje.\n"
    )

    mode = settings.otp_delivery.strip().lower()
    if mode == "log":
        if settings.app_environment.lower() == "production":
            raise EmailDeliveryError("El envío por consola no está permitido en producción.")
        logger.warning(
            "[OTP desarrollo] %s -> código %s (solo para pruebas locales)",
            to_email,
            code,
        )
        return

    if mode != "smtp":
        raise EmailDeliveryError(f"otp_delivery inválido: {settings.otp_delivery!r}")

    host = settings.smtp_host.strip()
    if not host:
        raise EmailDeliveryError(
            "SMTP no configurado. Define SMTP_HOST, SMTP_PORT, SMTP_USER y SMTP_PASSWORD en .env"
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, settings.smtp_port, timeout=30) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except OSError as exc:
        raise EmailDeliveryError(
            f"No se pudo conectar al servidor SMTP {host}:{settings.smtp_port} — {exc}"
        ) from exc
    except smtplib.SMTPException as exc:
        raise EmailDeliveryError(f"Error SMTP al enviar el correo: {exc}") from exc

    logger.info("OTP enviado por SMTP a %s", to_email)
