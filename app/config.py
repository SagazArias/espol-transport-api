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
        if self.jwt_secret.startswith("change-me"):
            raise ValueError("En producción define JWT_SECRET largo y aleatorio.")
        if self.expose_api_errors:
            object.__setattr__(self, "expose_api_errors", False)
        if self.access_token_expire_minutes > 60 * 24:
            object.__setattr__(self, "access_token_expire_minutes", 60 * 12)
        return self

    jwt_secret: str = "change-me-in-production-use-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12

    expose_api_errors: bool = True

    login_max_failed_attempts: int = 5
    login_lockout_minutes: int = 15

    recovery_max_failed_attempts: int = 5
    recovery_lockout_minutes: int = 15
    password_reset_token_minutes: int = 15

    recaptcha_secret_key: str = ""
    recaptcha_min_score: float = 0.5

    force_https_redirect: bool = False


settings = Settings()
