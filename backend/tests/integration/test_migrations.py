"""Initial Alembic migration lifecycle tests on temporary SQLite files."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from pytest import MonkeyPatch
from sqlalchemy import inspect, text

from nostalgiabox.config.settings import Settings
from nostalgiabox.persistence.database import create_engine

_BACKEND_ROOT = Path(__file__).parents[2]
_TABLES = {
    "alembic_version",
    "catalogue_items",
    "channels",
    "media_files",
    "media_items",
    "media_sources",
    "playable_renditions",
    "scan_issues",
    "scan_runs",
    "timeline_entries",
}


def test_initial_migration_upgrade_repeat_downgrade_and_reupgrade(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("NOSTALGIABOX_DATABASE_URL", database_url)
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))

    command.upgrade(config, "head")
    command.upgrade(config, "head")
    assert _table_names(database_url) == _TABLES
    assert _current_revision(database_url) == "20260810_0004"
    _assert_catalogue_foundation_schema(database_url)
    _assert_source_lifecycle_schema(database_url)
    _assert_scan_discovery_schema(database_url)

    command.downgrade(config, "base")
    assert _table_names(database_url) == {"alembic_version"}

    command.upgrade(config, "head")
    assert _table_names(database_url) == _TABLES


def _table_names(database_url: str) -> set[str]:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _current_revision(database_url: str) -> str | None:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def _assert_catalogue_foundation_schema(database_url: str) -> None:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        inspector = inspect(engine)
        locator_indexes = {
            index["name"]: (tuple(index["column_names"]), index["unique"])
            for index in inspector.get_indexes("media_files")
        }
        assert locator_indexes["ix_media_files_source_locator"] == (
            ("source_id", "normalized_relative_locator"),
            0,
        )
        assert inspector.get_unique_constraints("media_files") == []
        assert {
            constraint["name"] for constraint in inspector.get_check_constraints("media_files")
        }.issuperset(
            {
                "ck_media_files_id_nonblank",
                "ck_media_files_normalized_locator_nonblank",
                "ck_media_files_original_locator_nonblank",
            }
        )
        assert "ck_renditions_id_nonblank" in {
            constraint["name"]
            for constraint in inspector.get_check_constraints("playable_renditions")
        }
    finally:
        engine.dispose()


def _assert_source_lifecycle_schema(database_url: str) -> None:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("media_sources")}
        assert {
            "display_name",
            "configured_root",
            "enabled",
            "availability",
            "last_checked_utc_us",
            "last_successful_scan_utc_us",
            "current_error_code",
            "current_error_message",
            "retired_utc_us",
            "revision",
        }.issubset(columns)
        indexes = {index["name"] for index in inspector.get_indexes("media_sources")}
        assert "ix_media_sources_enabled_availability" in indexes
        with engine.connect() as connection:
            table_sql = connection.scalar(
                text(
                    "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'media_sources'"
                )
            )
        assert table_sql is not None
        for constraint_name in {
            "ck_media_sources_display_name_nonblank",
            "ck_media_sources_configured_root_nonblank",
            "ck_media_sources_enabled_boolean",
            "ck_media_sources_availability",
            "ck_media_sources_error_code_nonblank",
            "ck_media_sources_error_message_nonblank",
            "ck_media_sources_error_pair",
            "ck_media_sources_retired_disabled",
            "ck_media_sources_revision_positive",
        }:
            assert constraint_name in table_sql
    finally:
        engine.dispose()


def _assert_scan_discovery_schema(database_url: str) -> None:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        inspector = inspect(engine)
        file_columns = {column["name"] for column in inspector.get_columns("media_files")}
        assert {
            "presence",
            "size_bytes",
            "modified_time_ns",
            "device_id",
            "inode_id",
            "last_seen_generation",
            "first_observed_utc_us",
            "last_observed_utc_us",
            "missing_since_utc_us",
        }.issubset(file_columns)
        file_indexes = {index["name"]: index for index in inspector.get_indexes("media_files")}
        assert file_indexes["uq_media_files_present_source_locator"]["unique"] == 1
        run_indexes = {index["name"]: index for index in inspector.get_indexes("scan_runs")}
        assert run_indexes["uq_scan_runs_active_source"]["unique"] == 1
        assert "uq_scan_runs_source_generation" in {
            constraint["name"] for constraint in inspector.get_unique_constraints("scan_runs")
        }
        assert "uq_scan_issues_run_key" in {
            constraint["name"] for constraint in inspector.get_unique_constraints("scan_issues")
        }
    finally:
        engine.dispose()
