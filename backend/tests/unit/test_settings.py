"""Tests for typed runtime settings."""

from pathlib import Path

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
    assert settings.mpv_socket_path == Path("/run/nostalgiabox/mpv.sock")
    assert settings.mpv_command_timeout_seconds == 2.0
    assert settings.approved_local_media_roots == (Path("/srv/nostalgiabox/media"),)
    assert settings.scan_discovery_extensions == (
        ".mkv",
        ".mp4",
        ".m4v",
        ".avi",
        ".mov",
        ".webm",
        ".mpg",
        ".mpeg",
        ".ts",
        ".m2ts",
    )
    assert settings.scan_ignore_patterns == ()
    assert settings.scan_persistence_batch_size == 100
    assert settings.scan_progress_update_threshold == 50
    assert settings.scan_worker_concurrency == 2


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
    monkeypatch.setenv("NOSTALGIABOX_MPV_SOCKET_PATH", "/tmp/explicit-test.sock")
    monkeypatch.setenv("NOSTALGIABOX_MPV_COMMAND_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv(
        "NOSTALGIABOX_APPROVED_LOCAL_MEDIA_ROOTS",
        '["/srv/nostalgiabox/media", "/mnt/expert-media"]',
    )

    settings = Settings(_env_file=None)

    assert settings.environment == "production"
    assert settings.database_url == production_database_url
    assert settings.log_level == "DEBUG"
    assert settings.local_timezone == "UTC"
    assert settings.mpv_socket_path == Path("/tmp/explicit-test.sock")
    assert settings.mpv_command_timeout_seconds == 3.5
    assert settings.approved_local_media_roots == (
        Path("/srv/nostalgiabox/media"),
        Path("/mnt/expert-media"),
    )


def test_settings_reject_non_positive_mpv_timeout() -> None:
    with pytest.raises(ValidationError):
        Settings(mpv_command_timeout_seconds=0)


def test_settings_accept_explicit_expert_media_roots() -> None:
    roots = (Path("/srv/nostalgiabox/media"), Path("/mnt/expert-media"))

    settings = Settings(approved_local_media_roots=roots)

    assert settings.approved_local_media_roots == roots


@pytest.mark.parametrize(
    "roots",
    [(Path("relative"),), (Path("/duplicate"), Path("/duplicate"))],
)
def test_settings_reject_ambiguous_approved_media_roots(roots: tuple[Path, ...]) -> None:
    with pytest.raises(ValidationError, match="approved local media roots"):
        Settings(approved_local_media_roots=roots)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("scan_discovery_extensions", ()),
        ("scan_discovery_extensions", ("mkv",)),
        ("scan_discovery_extensions", (".MKV",)),
        ("scan_discovery_extensions", (".mkv", ".mkv")),
        ("scan_ignore_patterns", ("../escape",)),
        ("scan_ignore_patterns", ("/absolute",)),
        ("scan_persistence_batch_size", 0),
        ("scan_progress_update_threshold", 0),
        ("scan_worker_concurrency", 0),
        ("scan_worker_concurrency", 5),
    ],
)
def test_settings_reject_unsafe_or_unbounded_scan_policy(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({field: value})
