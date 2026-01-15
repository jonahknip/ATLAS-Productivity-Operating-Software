"""ATLAS configuration management."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "ATLAS"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./atlas.db"

    # Provider keys (BYOK)
    openai_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # Reliability engine caps (locked per spec)
    max_attempts_per_model: int = 2  # normal → json repair
    max_models_per_request: int = 3

    # Paths
    data_dir: Path = Path("./data")
    exports_dir: Path = Path("./exports")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
