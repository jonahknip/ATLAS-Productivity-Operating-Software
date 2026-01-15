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

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database - supports SQLite (local) or Postgres (production)
    # If DATABASE_URL is set (Railway), use Postgres; otherwise SQLite
    database_url: str = "sqlite+aiosqlite:///./atlas.db"

    # Security - API token for /v1/* routes
    api_token: str | None = None

    # CORS - comma-separated list of allowed origins
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Provider keys (BYOK)
    openai_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # Reliability engine caps (locked per spec)
    max_attempts_per_model: int = 2  # normal → json repair
    max_models_per_request: int = 3

    # Paths
    data_dir: Path = Path("./data")
    exports_dir: Path = Path("./exports")

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_postgres(self) -> bool:
        """Check if using Postgres (production) vs SQLite (local)."""
        return self.database_url.startswith("postgres")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
