from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# RFC 7518 §3.2: an HMAC key for SHA-256 must be at least as long as the hash.
MIN_JWT_SECRET_BYTES = 32
_DEFAULT_SECRET = "change-me-in-production"  # noqa: S105 - a placeholder, not a secret
LOCAL_ENVIRONMENTS = frozenset({"development", "test"})

# The privacy notice and terms a new account agrees to. Bump it whenever either
# text changes: consent is recorded against a version, and consent to a notice
# nobody can identify later is consent nobody can prove (DPDP Act 2023).
PRIVACY_NOTICE_VERSION = "2026-09-11"


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
    mongo_database: str = "iism_nsqf_master_data"

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

    # --- logging ---
    log_level: str = "INFO"
    # Defaults to `json` so a missing environment variable fails toward the
    # machine-readable format. `.env.example` sets `console` for development,
    # where a human is the reader.
    log_format: Literal["json", "console"] = "json"

    # --- privacy (DPDP Act 2023) ---
    privacy_notice_version: str = PRIVACY_NOTICE_VERSION
    # Analytics events carry no name, phone or email, but they are tied to an
    # account, and data kept "just in case" is data held without a purpose.
    analytics_retention_days: int = 365

    # --- abuse protection ---
    # Per minute. Signed-in requests are limited per *user*, anonymous ones per
    # IP: Indian mobile carriers put many subscribers behind one address (CGNAT),
    # and a per-IP limit alone would throttle strangers for each other.
    rate_limit_enabled: bool = True
    rate_limit_reads_per_minute: int = 300
    rate_limit_writes_per_minute: int = 60
    rate_limit_auth_per_minute: int = 30
    # MUST be true behind a load balancer. Otherwise every request appears to
    # come from the balancer itself and the whole platform shares one bucket.
    # False by default because trusting the header without a proxy in front lets
    # any caller choose their own identity for the limiter.
    rate_limit_trust_forwarded: bool = False
    # JSON only. A job description is a few kilobytes; nothing legitimate needs
    # more, and an unbounded body is a cheap way to exhaust a worker's memory.
    max_request_body_bytes: int = 256 * 1024

    # --- database pool ---
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout_seconds: int = 10
    # A runaway query holds a connection until it finishes. 0 disables it; the
    # Makefile does exactly that for the importer and the seed, which run
    # legitimately long statements through this same engine.
    db_statement_timeout_ms: int = 15000

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
        if self.db_echo:
            # `echo=True` makes SQLAlchemy attach its *own* raw StreamHandler
            # to `sqlalchemy.engine.Engine` -- bypassing the redaction filter
            # entirely -- and it logs bound parameters. `select(User).where(
            # User.phone == phone)` binds a phone number. Same class of leak as
            # exposing the OTP, so it gets the same startup refusal.
            raise ValueError("DB_ECHO must be false outside development")
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
