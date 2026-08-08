"""Typed application settings loaded from environment variables."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
