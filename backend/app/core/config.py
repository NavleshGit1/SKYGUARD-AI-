import os
import sys
from pydantic_settings import BaseSettings
from typing import List


def _require_env(key: str, default: str = None, allow_in_dev: bool = True) -> str:
    """
    Fetch an environment variable. In production, missing critical secrets raise
    an explicit error rather than silently falling back to an insecure default.
    """
    env = os.getenv("ENVIRONMENT", "development")
    value = os.getenv(key, default)
    if value is None or (env == "production" and value == default and not allow_in_dev):
        print(
            f"[FATAL] Required environment variable '{key}' is not set. "
            f"Copy .env.example to .env and set all required secrets before starting.",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


class Settings(BaseSettings):
    PROJECT_NAME: str = "SkyGuard AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # ── Environment ───────────────────────────────────────────────────────────
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "sih2026-skyguard-production-jwt-auth-secret-key-super-secure-token-256bit"
    )
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    TELEMETRY_HMAC_SECRET: str = (
        os.getenv("TELEMETRY_HMAC_SECRET")
        or os.getenv("HMAC_SECRET_KEY")
        or "sih2026-skyguard-shared-hmac-key-imd-defense-grade"
    )

    # ── Database (PostgreSQL + TimescaleDB) ────────────────────────────────────
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "skyguard_db")

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

    # ── CORS ──────────────────────────────────────────────────────────────────
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "allow"


settings = Settings()
