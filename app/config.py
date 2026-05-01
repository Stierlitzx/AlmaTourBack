from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

from pydantic import field_validator
from pydantic_settings import BaseSettings


def _normalize_database_url(raw_url: str) -> str:
    """Normalize common Postgres/Neon URLs for SQLAlchemy asyncpg.

    Accepts URLs copied from Neon dashboards such as:
    - postgresql://.../dbname?sslmode=require&channel_binding=require
    - postgres://.../dbname?sslmode=require

    and converts them to a format SQLAlchemy's async engine expects:
    - postgresql+asyncpg://.../dbname?ssl=require
    """
    raw_url = raw_url.strip().strip('"').strip("'")
    if raw_url.startswith("DATABASE_URL="):
        raw_url = raw_url.split("=", 1)[1].strip().strip('"').strip("'")

    parsed = urlparse(raw_url)
    scheme = parsed.scheme
    if scheme in {"postgres", "postgresql"}:
        scheme = "postgresql+asyncpg"

    query_parts: list[str] = []
    ssl_value = ""

    for part in filter(None, parsed.query.split("&")):
        key, sep, value = part.partition("=")
        if not sep:
            continue
        if key == "sslmode":
            ssl_value = value
            continue
        if key == "channel_binding":
            continue
        query_parts.append(f"{quote(key)}={quote(value)}")

    if ssl_value and not any(p.startswith("ssl=") for p in query_parts):
        query_parts.append(f"ssl={quote(ssl_value)}")

    return urlunparse(parsed._replace(scheme=scheme, query="&".join(query_parts)))


class Settings(BaseSettings):
    database_url: str = ""
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24h
    app_env: str = "development"
    cors_origins: str = "http://localhost:3000,http://localhost:8000"
    sentry_dsn: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @field_validator("database_url", mode="before")
    @classmethod
    def _validate_database_url(cls, value):
        if not value:
            return value
        return _normalize_database_url(str(value))

    class Config:
        env_file = Path(__file__).resolve().parent.parent / ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy `.env.example` to `.env` and provide a valid PostgreSQL/Neon connection string."
        )
    return settings
