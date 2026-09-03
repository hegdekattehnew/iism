from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# RFC 7518 §3.2: an HMAC key for SHA-256 must be at least as long as the hash.
MIN_JWT_SECRET_BYTES = 32
_DEFAULT_SECRET = "change-me-in-production"  # noqa: S105 - a placeholder, not a secret
LOCAL_ENVIRONMENTS = frozenset({"development", "test"})


class Settings(BaseSettings):
    """Environment-driven configuration. Never hardcode secrets (ADR-023)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    app_name: str = "Intelligent Integrated Skill Marketplace"
    app_version: str = "0.1.0"
    api_base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:3000"

    database_url: str = "postgresql+asyncpg://iism:iism@localhost:5433/iism"
    redis_url: str = "redis://localhost:6380/0"

    # Master of the raw NSQF feed (ADR-034). Postgres remains the operational
    # store; this is the source it is projected from, never read at request time.
    # Host port 27018, matching the 5433/6380 convention.
    mongo_url: str = "mongodb://iism:iism@localhost:27018/?authSource=admin"
    mongo_database: str = "nsqf"

    # Echo SQL only in development; noisy and leaks values into logs otherwise.
    db_echo: bool = False

    # --- auth (ADR-009, ADR-032) ---
    jwt_secret_key: str = _DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # --- one-time passcodes ---
    otp_length: int = 6
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    # Requests per phone per window. An unthrottled OTP endpoint is a
    # denial-of-wallet on the SMS bill, not merely a nuisance.
    otp_request_limit: int = 5
    otp_request_window_seconds: int = 900
    # Development only: return the code in the API response so the flow can be
    # exercised without an SMS provider. Must never be true outside development.
    otp_expose_in_response: bool = True

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @model_validator(mode="after")
    def _guard_production_secrets(self) -> "Settings":
        """Fail at startup rather than signing tokens with a weak or shared key.

        A short HMAC key weakens every token the system issues, and the default
        placeholder is public knowledge. Development is allowed to be lax; any
        other environment is not.
        """
        # Local and CI environments are allowed to be lax. Anything else —
        # staging included — must supply a real key.
        if self.environment in LOCAL_ENVIRONMENTS:
            return self
        if self.jwt_secret_key == _DEFAULT_SECRET:
            raise ValueError("JWT_SECRET_KEY must be set outside development")
        if len(self.jwt_secret_key.encode()) < MIN_JWT_SECRET_BYTES:
            raise ValueError(f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_BYTES} bytes")
        if self.otp_expose_in_response:
            raise ValueError("OTP_EXPOSE_IN_RESPONSE must be false outside development")
        return self

    @property
    def is_local(self) -> bool:
        return self.environment in LOCAL_ENVIRONMENTS

    @property
    def expose_otp(self) -> bool:
        """Belt and braces: the flag alone cannot leak codes outside local envs."""
        return self.otp_expose_in_response and self.is_local


@lru_cache
def get_settings() -> Settings:
    """Always access configuration through this, never a module-level singleton.

    An import-time singleton is bound before tests (or any caller) can override
    the environment, which silently points the engine at the wrong database.
    """
    return Settings()
