import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def verify_recaptcha(token: str | None, expected_action: str) -> None:
    secret = settings.recaptcha_secret_key.strip()
    if not secret:
        return
    if not token or not token.strip():
        raise ValueError("Verificación anti-bot requerida.")

    try:
        resp = httpx.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": secret, "response": token.strip()},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.exception("reCAPTCHA verification failed")
        raise ValueError("No se pudo validar reCAPTCHA. Intenta de nuevo.") from exc

    if not data.get("success"):
        raise ValueError("reCAPTCHA inválido.")
    score = data.get("score")
    if score is not None and float(score) < settings.recaptcha_min_score:
        raise ValueError("reCAPTCHA: actividad sospechosa detectada.")
