"""
Application configuration using Pydantic V2 BaseSettings.
Loads environment variables from the .env file at the backend root.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic import Field, AliasChoices

# Resolve the .env file path relative to this config file
# config.py is at backend/app/core/config.py → backend/.env
ENV_FILE_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    APP_ENV: str = "development"
    DEBUG: bool = True
    PROJECT_NAME: str = "Sakra-Finance"
    API_V1_STR: str = "/api/v1"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # ── CORS ─────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse comma-separated origins into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    # ── JWT ──────────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Encryption ───────────────────────────────────────────────
    AES_ENCRYPTION_KEY: str = Field(validation_alias=AliasChoices("AES_ENCRYPTION_KEY", "AES_KEY"))
    AADHAAR_SALT: str

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str
    REDIS_URL: str = ""

    # ── Email (Resend) ───────────────────────────────────────────
    RESEND_API_KEY: str
    SENDER_EMAIL: str = Field(validation_alias=AliasChoices("SENDER_EMAIL", "RESEND_FROM_EMAIL"))

    # ── AI Copilot ───────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    VECTOR_DB_URL: str = ""
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    AI_MAX_TOKENS: int = 1000
    AI_TEMPERATURE: float = 0.2

    # ── Performance Tuning (Production) ────────────────────────
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 300
    DATABASE_POOL_SIZE: int = 30
    DATABASE_MAX_OVERFLOW: int = 60
    DATABASE_POOL_TIMEOUT: int = 30
    ENABLE_GZIP: bool = True

    # ── Loan Closure ──────────────────────────────────────────────
    LOAN_CLOSURE_SECRET: str = ""


# Singleton settings instance
settings = Settings()

