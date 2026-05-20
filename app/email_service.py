import logging
import smtplib
import ssl
from email.message import EmailMessage

import resend

from app.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Email delivery failed."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


def _otp_subject() -> str:
    return "Código de verificación — ESPOL Transporte"


def _otp_body_plain(code: str) -> str:
    return (
        f"Hola,\n\n"
        f"Tu código de verificación para ESPOL Transporte es: {code}\n\n"
        f"Caduca en {settings.student_otp_ttl_minutes} minutos.\n\n"
        f"Si no solicitaste este código, ignora este mensaje.\n"
    )


def _otp_body_html(code: str) -> str:
    return (
        f"<p>Hola,</p>"
        f"<p>Tu código de verificación para <strong>ESPOL Transporte</strong> es:</p>"
        f"<p style=\"font-size:28px;font-weight:bold;letter-spacing:4px;\">{code}</p>"
        f"<p>Caduca en {settings.student_otp_ttl_minutes} minutos.</p>"
        f"<p>Si no solicitaste este código, ignora este mensaje.</p>"
    )


def _send_via_resend(to_email: str, subject: str, text: str, html: str) -> None:
    api_key = settings.resend_api_key.strip()
    if not api_key:
        raise EmailDeliveryError(
            "RESEND_API_KEY no está configurado. Obtén una clave en https://resend.com/api-keys"
        )

    from_addr = settings.resend_from.strip()
    if not from_addr:
        raise EmailDeliveryError("RESEND_FROM no está configurado (ej. ESPOL Transporte <noreply@tudominio.com>).")

    resend.api_key = api_key

    try:
        result = resend.Emails.send(
            {
                "from": from_addr,
                "to": [to_email],
                "subject": subject,
                "text": text,
                "html": html,
            }
        )
        email_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", result)
        logger.info("OTP enviado vía Resend a %s (id=%s)", to_email, email_id)
    except Exception as exc:
        raise EmailDeliveryError(f"Resend no pudo enviar el correo: {exc}", cause=exc) from exc


def _smtp_connection():
    host = settings.smtp_host.strip()
    port = settings.smtp_port
    if not host:
        raise EmailDeliveryError("SMTP_HOST no está configurado.")

    timeout = settings.smtp_timeout_seconds
    use_ssl = settings.smtp_use_ssl or port == 465

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
        raise EmailDeliveryError(f"No se pudo conectar a SMTP {host}:{port}: {exc}", cause=exc) from exc
    except smtplib.SMTPException as exc:
        raise EmailDeliveryError(f"Error SMTP: {exc}", cause=exc) from exc


def _send_via_smtp(to_email: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(body)

    smtp = _smtp_connection()
    try:
        smtp.send_message(msg)
    except smtplib.SMTPException as exc:
        raise EmailDeliveryError(f"Error al enviar por SMTP: {exc}", cause=exc) from exc
    finally:
        try:
            smtp.quit()
        except Exception:
            pass
    logger.info("Correo enviado por SMTP a %s", to_email)


def send_student_verification_email(to_email: str, code: str) -> None:
    subject = _otp_subject()
    text = _otp_body_plain(code)
    html = _otp_body_html(code)

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

    try:
        if mode == "resend":
            _send_via_resend(to_email, subject, text, html)
        elif mode == "smtp":
            _send_via_smtp(to_email, subject, text)
        else:
            raise EmailDeliveryError(
                f"otp_delivery inválido: {settings.otp_delivery!r}. Usa 'resend', 'smtp' o 'log'."
            )
    except EmailDeliveryError:
        raise
    except Exception as exc:
        raise EmailDeliveryError(f"Fallo inesperado al enviar correo: {exc}", cause=exc) from exc
