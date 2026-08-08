"""Typed application settings loaded from environment variables."""

from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from nostalgiabox.config.database import is_in_memory_sqlite_url


class Settings(BaseSettings):
    """NostalgiaBox runtime settings with local development defaults."""

    model_config = SettingsConfigDict(
        env_prefix="NOSTALGIABOX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = Field(default="sqlite+pysqlite:///:memory:", min_length=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    local_timezone: str = Field(default="Europe/London", min_length=1)
    mpv_socket_path: Path = Path("/run/nostalgiabox/mpv.sock")
    mpv_command_timeout_seconds: float = Field(default=2.0, gt=0)

    @model_validator(mode="after")
    def require_persistent_production_database(self) -> Self:
        """Reject ephemeral persistence when running in production."""
        if self.environment == "production" and is_in_memory_sqlite_url(self.database_url):
            message = (
                "Production configuration requires an explicitly configured persistent database "
                "URL; an in-memory SQLite database is not allowed."
            )
            raise ValueError(message)
        return self
