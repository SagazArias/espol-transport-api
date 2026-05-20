import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """SMTP send failed."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


def _smtp_connection():
    host = settings.smtp_host.strip()
    port = settings.smtp_port
    if not host:
        raise EmailDeliveryError("SMTP_HOST no está configurado.")

    timeout = settings.smtp_timeout_seconds
    use_ssl = settings.smtp_use_ssl or port == 465

    logger.info(
        "SMTP connect host=%s port=%s ssl=%s starttls=%s user_set=%s",
        host,
        port,
        use_ssl,
        settings.smtp_use_tls and not use_ssl,
        bool(settings.smtp_user),
    )

    try:
        if use_ssl:
            context = ssl.create_default_context()
            smtp = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
        else:
            smtp = smtplib.SMTP(host, port, timeout=timeout)
            if settings.smtp_use_tls:
                context = ssl.create_default_context()
                smtp.starttls(context=context)
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        return smtp
    except OSError as exc:
        raise EmailDeliveryError(
            f"No se pudo conectar a {host}:{port}. En Render usa puerto 587 (TLS) o 465 (SSL). Detalle: {exc}",
            cause=exc,
        ) from exc
    except smtplib.SMTPException as exc:
        raise EmailDeliveryError(f"Error SMTP al conectar o autenticar: {exc}", cause=exc) from exc


def _send_email(to_email: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(body)

    smtp = _smtp_connection()
    try:
        smtp.send_message(msg)
    except smtplib.SMTPException as exc:
        raise EmailDeliveryError(f"Error al enviar el mensaje: {exc}", cause=exc) from exc
    finally:
        try:
            smtp.quit()
        except Exception:
            pass

    logger.info("Correo enviado por SMTP a %s (asunto: %s)", to_email, subject)


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

    try:
        _send_email(to_email, subject, body)
    except EmailDeliveryError:
        raise
    except Exception as exc:
        raise EmailDeliveryError(f"Fallo inesperado al enviar correo: {exc}", cause=exc) from exc
