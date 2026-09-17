"""
Application configuration.

All settings are read from environment variables (see .env.example at the
project root). We use pydantic-settings so that:
  - required values fail loudly at startup instead of silently at query time
  - types are validated (e.g. DB_PORT must be an int)
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at the project root (one level above backend/), so this works
# whether uvicorn is started from the repo root or from inside backend/.
ROOT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # --- Database ---
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "icestream"
    db_user: str = "icestream"
    db_password: str = "icestream"

    # --- App ---
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=str(ROOT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
