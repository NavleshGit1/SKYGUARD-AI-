import os
import sys
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from typing import List

# Explicitly load .env from project root
_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_env_path = os.path.join(_root_dir, ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)


class Settings(BaseSettings):
    PROJECT_NAME: str = "SkyGuard AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # ── Environment ───────────────────────────────────────────────────────────
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")

    # ── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "93eb1a11f9678e43e62746a75b0bde4c2c00a48cf464d68ce90182b09a9b2791")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    TELEMETRY_HMAC_SECRET: str = os.getenv("TELEMETRY_HMAC_SECRET", "eb91aa8b28b4208b596f241c27b45cf73d0212ba4bc6ec0fa4c9c72baaf83c38")

    # ── Database (PostgreSQL + TimescaleDB) ────────────────────────────────────
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "skyguard_db")

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        # Check for Render / Cloud Managed PostgreSQL URL
        db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
        if db_url:
            # SQLAlchemy 2.x requires postgresql:// instead of legacy postgres://
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            return db_url

        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # ── CORS ──────────────────────────────────────────────────────────────────
    @property
    def CORS_ORIGINS(self) -> List[str]:
        origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8000",
            "*",
        ]
        frontend_url = os.getenv("FRONTEND_URL")
        if frontend_url:
            origins.append(frontend_url.rstrip("/"))
        return origins

    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "*",
    ]

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "allow"


settings = Settings()
