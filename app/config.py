from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_environment: str = "development"

    database_url: str = "postgresql+psycopg://espol:espol_dev@localhost:5432/espol_transport"

    @model_validator(mode="after")
    def normalize_database_url(self) -> "Settings":
        u = self.database_url
        if u.startswith("postgresql://") and not u.startswith("postgresql+psycopg://"):
            self.database_url = u.replace("postgresql://", "postgresql+psycopg://", 1)
        return self

    @model_validator(mode="after")
    def production_safety(self) -> "Settings":
        if self.app_environment.lower() != "production":
            return self
        if self.otp_delivery.lower() != "smtp":
            raise ValueError("En producción OTP_DELIVERY debe ser 'smtp' (correo real).")
        if not self.smtp_host.strip():
            raise ValueError("En producción configura SMTP_HOST y credenciales SMTP.")
        if self.jwt_secret.startswith("change-me"):
            raise ValueError("En producción define JWT_SECRET largo y aleatorio.")
        if self.expose_dev_otp:
            object.__setattr__(self, "expose_dev_otp", False)
        if self.expose_api_errors:
            object.__setattr__(self, "expose_api_errors", False)
        if self.access_token_expire_minutes > 60 * 24:
            object.__setattr__(self, "access_token_expire_minutes", 60 * 12)
        return self

    jwt_secret: str = "change-me-in-production-use-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12

    otp_delivery: str = "smtp"
    expose_dev_otp: bool = False
    expose_api_errors: bool = True

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "espol-transport@localhost"
    smtp_use_tls: bool = True

    student_otp_ttl_minutes: int = 15
    student_otp_resend_seconds: int = 60

    login_max_failed_attempts: int = 5
    login_lockout_minutes: int = 15

    recaptcha_secret_key: str = ""
    recaptcha_min_score: float = 0.5

    force_https_redirect: bool = False


settings = Settings()
