import hashlib
import hmac
import secrets

from app.config import settings


def generate_six_digit_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(email: str, code: str) -> str:
    key = settings.jwt_secret.encode("utf-8")
    msg = f"{email.lower().strip()}:{code}".encode("utf-8")
    return hashlib.sha256(hmac.new(key, msg, hashlib.sha256).digest()).hexdigest()


def verify_otp(email: str, code: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(email, code), code_hash)
