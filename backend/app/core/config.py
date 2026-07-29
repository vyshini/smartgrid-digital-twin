"""
Application configuration, loaded from environment variables / .env file.
Single source of truth for all runtime settings — nothing else in the codebase
should read os.environ directly.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    PROJECT_NAME: str = "Quantum-AI Digital Twin — Indian Smart Grid"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    API_V1_PREFIX: str = "/api/v1"
    ML_DATA_DIR: str = "ml-training/data"
    DEBUG: bool = False

    # --- Security / JWT ---
    JWT_SECRET_KEY: str = Field(..., description="Signing key for access/refresh tokens")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Database ---
    DATABASE_URL: PostgresDsn
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # --- Redis ---
    REDIS_URL: RedisDsn = "redis://localhost:6379/0"

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _assert_psycopg(cls, v: str) -> str:
        # We standardize on Psycopg 3's async driver for the async SQLAlchemy engine.
        # (Switched from asyncpg — psycopg[binary] has far more reliable prebuilt
        # wheel coverage on Windows, avoiding the "Microsoft Visual C++ 14.0 required"
        # build failure asyncpg can hit when no matching wheel exists.)
        if isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — import this, not Settings() directly."""
    return Settings()
