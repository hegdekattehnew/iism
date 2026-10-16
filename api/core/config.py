from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# RFC 7518 §3.2: an HMAC key for SHA-256 must be at least as long as the hash.
MIN_JWT_SECRET_BYTES = 32
_DEFAULT_SECRET = "change-me-in-production"  # noqa: S105 - a placeholder, not a secret
LOCAL_ENVIRONMENTS = frozenset({"development", "test"})

# The privacy notice and terms a new account agrees to. Bump it whenever either
# text changes: consent is recorded against a version, and consent to a notice
# nobody can identify later is consent nobody can prove (DPDP Act 2023).
PRIVACY_NOTICE_VERSION = "2026-10-17"


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
    # A closed set, not a bare `str`: `jwt.decode` is called with whatever this
    # says, and PyJWT accepts "none" as a literal algorithm name. A bare `str`
    # makes a misconfigured environment variable an unsigned-token hole rather
    # than a startup validation error.
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
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
    # The wait between two requests for one phone or address. The budget above
    # stops a flood over fifteen minutes; this stops the double tap and the
    # impatient fourth press, and it is what the forms count down from. 0 turns
    # it off (the test suite does, as it does the request limiter).
    otp_resend_cooldown_seconds: int = 30
    # Development only: return the code in the API response so the flow can be
    # exercised without an SMS provider. Must never be true outside development.
    otp_expose_in_response: bool = True

    # --- store-reviewer sign-in (Sprint 65, BL-15.8, ADR-076) ---
    # Both app stores reject an app their reviewer cannot sign in to, and a code sent to a phone the
    # reviewer does not hold cannot reach them. This is a **named exception**, off by default: when
    # the switch is on, a code request for one of the listed phones stores `reviewer_code` instead
    # of a generated one and sends no SMS. Nothing else changes: every other number takes the normal
    # path, the attempt cap and request budget still apply, `otp_expose_in_response` is still
    # refused outside development, and a staff or organisation account is refused at verification.
    reviewer_login_enabled: bool = False
    reviewer_phones: str = ""  # comma-separated; normalised by identity, the owner of that rule
    reviewer_code: str = ""  # a secret from the environment, `otp_length` digits

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
    # Notifications are the one place the product keeps what it has *said* to a person
    # (Sprint 49). Delivered email and read in-app notices go after this many days;
    # an in-app notice nobody has opened is kept twice as long, because it may be an
    # offer they have not seen. At least a week: nothing that reads the table looks
    # back further than a day, and a shorter floor would only be a way to lose a notice
    # before a person could.
    notification_retention_days: int = Field(default=90, ge=7)

    # --- grievances and contact messages (Sprint 57, ADR-067) ---
    # What the grievance page promises, in one place so the page and the operator's overdue badge
    # cannot disagree: acknowledged within a day, resolved within fifteen.
    grievance_acknowledge_hours: int = Field(default=24, ge=1)
    grievance_resolve_days: int = Field(default=15, ge=1)
    # A closed grievance is kept this long after it was closed, then deleted; an open one never is.
    grievance_retention_days: int = Field(default=365, ge=30)
    # Submissions an address, an account or a reply address may make in an hour. The form is public
    # and writes a row: it is a spam sink unless somebody says how much.
    grievance_submissions_per_hour: int = Field(default=5, ge=0)

    # Reports about listings (Sprint 59, ADR-069). One person may file this many a day (0 turns it
    # off, as in the test suite); a closed report is kept this long after it was closed, an open one
    # on a live listing never is.
    report_submissions_per_day: int = Field(default=10, ge=0)
    report_retention_days: int = Field(default=365, ge=30)

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
    # A bulk upload (Sprint 51, ADR-063) is a spreadsheet, not a form: 200 rows with long
    # descriptions is a few hundred kilobytes, so those two paths (and only those) take this
    # larger body. Every other route keeps the limit above.
    max_bulk_body_bytes: int = 2 * 1024 * 1024
    # Rows per uploaded file, and rows an organisation may create in a rolling 24 hours -- lower
    # until an operator has verified it. Drafts are invisible, so the cap bounds clutter and
    # abuse of the write path, not what a visitor can see; publishing is a separate step.
    bulk_max_rows: int = Field(default=200, ge=1)
    bulk_rows_per_day_unverified: int = Field(default=100, ge=1)
    bulk_rows_per_day_verified: int = Field(default=500, ge=1)
    # An agency's cohort is larger than an organisation's vacancy list (Sprint 61, BL-14.10).
    enrolment_max_rows: int = Field(default=1000, ge=1)
    # The oldest installed mobile app each store build may be, per platform (Sprint 62, ADR-072).
    # An app below it is answered 426 and shown an update screen; "0.0.0" retires nothing. Raised
    # only when a breaking API change ships, because an installed app cannot be updated on demand.
    mobile_min_version_android: str = "0.0.0"
    mobile_min_version_ios: str = "0.0.0"

    # Applying is cheap for a candidate and expensive for an employer reading
    # the inbox. The per-minute write limit stops a script; this stops a day of
    # patient spraying, which is what actually ruins an inbox.
    max_applications_per_day: int = 50
    max_course_interests_per_day: int = 50
    # Creating a tenant publishes a public organisation page and can
    # publish listings, and until Sprint 26 it was the one write path
    # here with no cap at all. Rolling 24 hours, like its siblings.
    max_organisations_per_day: int = 5
    # Job alerts (Sprint 27). Both caps exist so a busy Monday does not
    # become the reason somebody stops reading their notifications: at
    # most this many people hear about any one vacancy, and at most this
    # many vacancies reach any one person in a rolling day.
    max_alerts_per_job: int = 25
    max_alerts_per_candidate_per_day: int = 5

    # --- matching weights (Sprint 33, BL-2.1) ---
    # `scoring.py` stays pure and never reads these -- `ScoreWeights` is a
    # value `matching.service.weights_from_settings()` builds from them and
    # passes in. Defaults are the numbers the scorer has used since Sprint 10;
    # `make evaluate` is bit-identical against them.
    match_weight_coverage: float = 0.75
    match_weight_level: float = 0.08
    match_weight_experience: float = 0.07
    match_weight_evidence_share: float = 0.10
    match_mandatory_gap_cap: float = 0.45
    # Below this coverage, the mandatory-gap cap itself tapers down rather
    # than holding flat -- a job whose only overlap is one generic,
    # non-distinctive standard should not read as the same near-miss a
    # genuinely one-standard-short strong match gets.
    match_min_coverage_for_cap: float = 0.40
    match_experience_taper_years: float = 3.0
    # Sprint 36, BL-5.2. Zero: additive on top of the four above, not carved
    # out of them, and turning it up is a deliberate, separately-measured
    # re-tune this story explicitly defers -- `make evaluate` must stay
    # bit-identical while this is 0.
    match_weight_semantic: float = 0.0
    # Sprint 49 (ADR-056). How many vacancies (for a candidate) or candidates (for one
    # vacancy) survive retrieval to be scored. They are the K *best* by a bound on the
    # score, not an arbitrary K, so raising it buys recall at the price of scoring
    # more rows; the benchmark (`make benchmark`) is how to choose. At least 20,
    # the page size, or a page could not be filled.
    match_retrieval_limit: int = Field(default=500, ge=20)

    # --- embeddings (ADR-013, ADR-031) ---
    # `"hashing"` (the placeholder, `HashingEmbeddingProvider`) is the default
    # everywhere -- dev, test, CI -- so adding the real model's dependency does
    # not by itself change any environment's behaviour. Set to
    # `"sentence_transformer"` to load the real, ADR-mandated model; that pulls
    # in a ~470 MB download on first use, so it is an explicit, separate
    # decision per environment, not something this setting's own default makes
    # for anyone.
    embedding_provider: str = "hashing"

    # --- database pool ---
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout_seconds: int = 10
    # A runaway query holds a connection until it finishes. 0 disables it; the
    # Makefile does exactly that for the importer and the seed, which run
    # legitimately long statements through this same engine.
    db_statement_timeout_ms: int = 15000
    # Postgres compiles a query to machine code once its estimated cost passes
    # `jit_above_cost` (100,000), and for the few heavy aggregates this product runs it costs
    # more than it saves: the batched programme report took 37 s for 10,000 candidates with it
    # and 18 s without, ~600 ms of it in compilation per chunk (Sprint 50). Every cheap query is
    # unaffected either way. Off by default, which is the standard advice for an OLTP service; set
    # true to put the server's own default back.
    db_jit: bool = False

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

    @model_validator(mode="after")
    def _guard_reviewer_login(self) -> "Settings":
        """A reviewer exception that is on must be a small, named, non-trivial one, in every
        environment; outside development it must also not be a guessable code."""
        if not self.reviewer_login_enabled:
            return self
        phones = [p for p in (x.strip() for x in self.reviewer_phones.split(",")) if p]
        if not phones:
            raise ValueError(
                "REVIEWER_PHONES must name at least one phone when reviewer login is on"
            )
        if len(phones) > MAX_REVIEWER_PHONES:
            raise ValueError(f"REVIEWER_PHONES may name at most {MAX_REVIEWER_PHONES} phones")
        if any(sum(ch.isdigit() for ch in p) < 10 for p in phones):
            raise ValueError("every REVIEWER_PHONES entry must be a phone number")
        code = self.reviewer_code
        if len(code) != self.otp_length or not code.isdigit():
            raise ValueError(f"REVIEWER_CODE must be exactly {self.otp_length} digits")
        if not self.is_local and _is_guessable(code):
            raise ValueError("REVIEWER_CODE is too easy to guess; choose another")
        return self

    @property
    def is_local(self) -> bool:
        return self.environment in LOCAL_ENVIRONMENTS

    @property
    def expose_otp(self) -> bool:
        """Belt and braces: the flag alone cannot leak codes outside local envs."""
        return self.otp_expose_in_response and self.is_local


MAX_REVIEWER_PHONES = 5


def _is_guessable(code: str) -> bool:
    """All one digit, or a straight run up or down: the first things anybody tries."""
    if len(set(code)) == 1:
        return True
    steps = {int(b) - int(a) for a, b in zip(code, code[1:], strict=False)}
    return steps in ({1}, {-1})


@lru_cache
def get_settings() -> Settings:
    """Always access configuration through this, never a module-level singleton.

    An import-time singleton is bound before tests (or any caller) can override
    the environment, which silently points the engine at the wrong database.
    """
    return Settings()
