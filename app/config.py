from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    app_base_url: str = "http://localhost:8000"

    database_url: str = "postgresql+asyncpg://iism:iism@localhost:5432/iism"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    email_verification_token_expire_hours: int = 24
    password_reset_token_expire_hours: int = 1

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-5"


settings = Settings()
