import os
import sys
import secrets
from pydantic_settings import BaseSettings
from typing import List, Union


def _get_secret_with_fallback(key: str, default: str = "") -> str:
    val = os.getenv(key, default)
    if not val:
        # Fallback generated token for zero-friction local/development deployments
        val = secrets.token_hex(32)
    return val


class Settings(BaseSettings):
    PROJECT_NAME: str = "SkyGuard AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # ── Environment ───────────────────────────────────────────────────────────
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "93eb1a11f9678e43e62746a75b0bde4c2c00a48cf464d68ce90182b09a9b2791")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    TELEMETRY_HMAC_SECRET: str = os.getenv("TELEMETRY_HMAC_SECRET", "eb91aa8b28b4208b596f241c27b45cf73d0212ba4bc6ec0fa4c9c72baaf83c38")

    # ── Database (Auto-adapts to Render, Neon, Supabase, Timescale, or SQLite) ──
    DATABASE_URL: str = os.getenv("DATABASE_URL", os.getenv("POSTGRES_URL", ""))
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "skyguard_db")

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        # 1. External Render / Supabase / Neon connection URL
        if self.DATABASE_URL:
            uri = self.DATABASE_URL
            # Normalize deprecated postgres:// prefix to postgresql:// for SQLAlchemy 2.0
            if uri.startswith("postgres://"):
                uri = uri.replace("postgres://", "postgresql://", 1)
            return uri
        
        # 2. SQLite Explicit fallback
        if self.POSTGRES_SERVER.lower() in ("sqlite", "local"):
            return "sqlite:///./data/skyguard_local.db"

        # 3. Standard TimescaleDB / PostgreSQL parameters
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Redis (Graceful fallback if not present on Free Tier) ─────────────────
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # ── Single-Container Embedded Telemetry Streamer ──────────────────────────
    # Essential for Render Free Tier single web container deployments
    ENABLE_EMBEDDED_SIMULATOR: bool = os.getenv("ENABLE_EMBEDDED_SIMULATOR", "True").lower() in ("true", "1", "t")
    SIMULATOR_TICK_SECONDS: float = float(os.getenv("SIMULATOR_TICK_SECONDS", "2.0"))

    # ── CORS (Dynamic for Vercel Frontends & Custom Domains) ───────────────────
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "")

    @property
    def BACKEND_CORS_ORIGINS(self) -> List[str]:
        base_origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8000",
            "https://localhost:3000",
            "https://localhost:5173",
        ]
        if self.CORS_ORIGINS:
            custom = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
            base_origins.extend(custom)
        
        # Allow all Vercel previews and deployments when not explicitly restricted
        if self.ENVIRONMENT in ("development", "dev", "production", "preview"):
            base_origins.append("*")
            
        return list(set(base_origins))

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "allow"


settings = Settings()
