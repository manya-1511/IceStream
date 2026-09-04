"""
Application configuration.

Loaded from environment variables (or a local .env file for development).
This is the single source of truth for configuration values across the
backend — no service should hardcode hosts, ports, or credentials.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_env: str = "development"
    app_name: str = "IceStream API"
    app_version: str = "0.1.0"
    debug: bool = True

    # --- PostgreSQL ---
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "icestream"
    postgres_user: str = "icestream"
    postgres_password: str = "icestream_dev_password"

    # --- Redis ---
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    # --- Kafka ---
    kafka_bootstrap_servers: str = "kafka:9092"

    # --- MinIO ---
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "icestream_minio"
    minio_secret_key: str = "icestream_minio_secret"
    minio_bucket: str = "icestream-warehouse"
    minio_use_ssl: bool = False

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection string (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Sync SQLAlchemy connection string (psycopg2 driver) — used by Alembic."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — avoids re-parsing env vars on every call."""
    return Settings()
