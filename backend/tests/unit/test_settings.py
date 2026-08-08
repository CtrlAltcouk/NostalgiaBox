"""Tests for typed runtime settings."""

from pytest import MonkeyPatch

from nostalgiabox.config.settings import Settings


def test_settings_have_safe_development_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.database_url == "sqlite+pysqlite:///:memory:"
    assert settings.log_level == "INFO"
    assert settings.local_timezone == "Europe/London"


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
