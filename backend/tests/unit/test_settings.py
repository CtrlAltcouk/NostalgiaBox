"""Tests for typed runtime settings."""

import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from nostalgiabox.config.settings import Settings


def test_settings_have_safe_development_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.database_url == "sqlite+pysqlite:///:memory:"
    assert settings.log_level == "INFO"
    assert settings.local_timezone == "Europe/London"


def test_test_environment_can_use_isolated_in_memory_database() -> None:
    settings = Settings(environment="test", database_url="sqlite+pysqlite:///:memory:")

    assert settings.environment == "test"
    assert settings.database_url == "sqlite+pysqlite:///:memory:"


def test_production_rejects_default_in_memory_database() -> None:
    with pytest.raises(
        ValidationError,
        match="Production configuration requires an explicitly configured persistent database URL",
    ):
        Settings(environment="production")


@pytest.mark.parametrize(
    "database_url",
    ["sqlite://", "sqlite+pysqlite:///file:memdb1?mode=memory&cache=shared&uri=true"],
)
def test_production_rejects_other_in_memory_sqlite_forms(database_url: str) -> None:
    with pytest.raises(ValidationError, match="an in-memory SQLite database is not allowed"):
        Settings(environment="production", database_url=database_url)


def test_production_accepts_intended_persistent_sqlite_url() -> None:
    database_url = "sqlite:////var/lib/nostalgiabox/nostalgiabox.db"

    settings = Settings(environment="production", database_url=database_url)

    assert settings.database_url == database_url


def test_settings_can_be_overridden_by_environment(monkeypatch: MonkeyPatch) -> None:
    production_database_url = "sqlite:////var/lib/nostalgiabox/nostalgiabox.db"
    monkeypatch.setenv("NOSTALGIABOX_ENVIRONMENT", "production")
    monkeypatch.setenv("NOSTALGIABOX_DATABASE_URL", production_database_url)
    monkeypatch.setenv("NOSTALGIABOX_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("NOSTALGIABOX_LOCAL_TIMEZONE", "UTC")

    settings = Settings(_env_file=None)

    assert settings.environment == "production"
    assert settings.database_url == production_database_url
    assert settings.log_level == "DEBUG"
    assert settings.local_timezone == "UTC"
