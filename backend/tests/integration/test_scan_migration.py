"""Task 3.3 lossless scanner migration and legacy locator compatibility."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pytest import MonkeyPatch
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from nostalgiabox.config.settings import Settings
from nostalgiabox.domain import ChannelId, FilePresenceState, MediaFileId
from nostalgiabox.persistence.catalogue_repositories import SqlAlchemyMediaFileRepository
from nostalgiabox.persistence.database import create_engine, create_session_factory
from nostalgiabox.persistence.runtime_sources import SqlAlchemyRuntimeDataSource

_BACKEND_ROOT = Path(__file__).parents[2]
_TASK32_REVISION = "20260810_0003"


def test_populated_task32_upgrade_downgrade_reupgrade_preserves_legacy_rows(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'scan-migration.db'}"
    monkeypatch.setenv("NOSTALGIABOX_DATABASE_URL", database_url)
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    command.upgrade(config, _TASK32_REVISION)
    _seed_task32(database_url)
    before = _task32_rows(database_url)

    command.upgrade(config, "head")

    assert _task32_rows(database_url) == before
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        with create_session_factory(engine)() as session:
            repository = SqlAlchemyMediaFileRepository(session)
            for identifier in ("file-unique", "file-duplicate-1", "file-duplicate-2"):
                media_file = repository.get_by_id(MediaFileId(identifier))
                assert media_file is not None
                assert media_file.presence is FilePresenceState.UNCLASSIFIED
                assert media_file.size_bytes is None
                assert media_file.modified_time_ns is None
                assert media_file.last_seen_generation is None
        runtime = SqlAlchemyRuntimeDataSource(create_session_factory(engine))
        assert runtime.load(ChannelId("channel-1")).entries[0].media_item_id.value == "legacy-media"
        assert runtime.get_path(runtime.load(ChannelId("channel-1")).entries[0].media_item_id) == (
            "/legacy/media.mkv"
        )
        indexes = {index["name"] for index in inspect(engine).get_indexes("media_files")}
        assert "uq_media_files_present_source_locator" in indexes
    finally:
        engine.dispose()

    command.downgrade(config, _TASK32_REVISION)
    assert _task32_rows(database_url) == before
    assert set(_columns(database_url, "media_files")) == {
        "id",
        "source_id",
        "normalized_relative_locator",
        "original_relative_locator",
    }

    command.upgrade(config, "head")
    assert _task32_rows(database_url) == before


def test_partial_present_uniqueness_allows_legacy_and_missing_rows(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'scan-constraints.db'}"
    monkeypatch.setenv("NOSTALGIABOX_DATABASE_URL", database_url)
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    command.upgrade(config, _TASK32_REVISION)
    _seed_task32(database_url)
    command.upgrade(config, "head")
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO media_files "
                    "(id, source_id, normalized_relative_locator, original_relative_locator) "
                    "VALUES ('legacy-extra', 'source-1', 'duplicate.mkv', 'duplicate.mkv')"
                )
            )
            _insert_classified(connection, "missing", "missing", "duplicate.mkv")
            _insert_classified(connection, "present-1", "present", "duplicate.mkv")
        with pytest.raises(IntegrityError), engine.begin() as connection:
            _insert_classified(connection, "present-2", "present", "duplicate.mkv")
    finally:
        engine.dispose()


def _insert_classified(
    connection: Connection, identifier: str, presence: str, locator: str
) -> None:
    missing = 100 if presence == "missing" else None
    connection.execute(
        text(
            "INSERT INTO media_files "
            "(id, source_id, normalized_relative_locator, original_relative_locator, presence, "
            "size_bytes, modified_time_ns, last_seen_generation, first_observed_utc_us, "
            "last_observed_utc_us, missing_since_utc_us) "
            "VALUES (:id, 'source-1', :locator, :locator, :presence, 1, 2, 1, 10, 10, :missing)"
        ),
        {
            "id": identifier,
            "locator": locator,
            "presence": presence,
            "missing": missing,
        },
    )


def _seed_task32(database_url: str) -> None:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO media_items VALUES "
                    "('legacy-media', 'Legacy', 60000000, '/legacy/media.mkv')"
                )
            )
            connection.execute(text("INSERT INTO channels VALUES ('channel-1', 1, 'Channel 001')"))
            connection.execute(
                text(
                    "INSERT INTO timeline_entries VALUES "
                    "('entry-1', 'channel-1', 'legacy-media', 'programme', 0, 60000000)"
                )
            )
            connection.execute(
                text("INSERT INTO catalogue_items VALUES ('legacy-media'), ('catalogue-2')")
            )
            connection.execute(
                text(
                    "INSERT INTO media_sources "
                    "(id, kind, display_name, configured_root, enabled, availability, revision) "
                    "VALUES ('source-1', 'local', 'Source', '/approved/source', 1, 'unknown', 1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO media_files "
                    "(id, source_id, normalized_relative_locator, "
                    "original_relative_locator) VALUES "
                    "('file-unique', 'source-1', 'unique.mkv', 'unique.mkv'), "
                    "('file-duplicate-1', 'source-1', 'duplicate.mkv', 'duplicate.mkv'), "
                    "('file-duplicate-2', 'source-1', 'duplicate.mkv', 'duplicate.mkv')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO playable_renditions VALUES "
                    "('rendition-1', 'legacy-media', 'file-duplicate-1', 0, 10, 10, 0, 0), "
                    "('rendition-2', 'catalogue-2', 'file-duplicate-2', 0, 10, 10, 0, 0)"
                )
            )
    finally:
        engine.dispose()


def _task32_rows(database_url: str) -> dict[str, tuple[tuple[object, ...], ...]]:
    queries = {
        "media_items": "SELECT id, title, duration_us, path FROM media_items ORDER BY id",
        "channels": "SELECT id, number, name FROM channels ORDER BY id",
        "timeline_entries": "SELECT * FROM timeline_entries ORDER BY id",
        "catalogue_items": "SELECT id FROM catalogue_items ORDER BY id",
        "media_sources": "SELECT * FROM media_sources ORDER BY id",
        "media_files": (
            "SELECT id, source_id, normalized_relative_locator, original_relative_locator "
            "FROM media_files ORDER BY id"
        ),
        "playable_renditions": "SELECT * FROM playable_renditions ORDER BY id",
    }
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        with engine.connect() as connection:
            return {
                name: tuple(tuple(row) for row in connection.execute(text(query)))
                for name, query in queries.items()
            }
    finally:
        engine.dispose()


def _columns(database_url: str, table_name: str) -> tuple[str, ...]:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        return tuple(column["name"] for column in inspect(engine).get_columns(table_name))
    finally:
        engine.dispose()
