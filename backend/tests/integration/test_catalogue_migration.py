"""Phase 2 populated-database migration and compatibility lifecycle proof."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pytest import MonkeyPatch
from sqlalchemy import inspect, text

from nostalgiabox.application.runtime import ChannelRuntime
from nostalgiabox.config.settings import Settings
from nostalgiabox.persistence.database import create_engine, create_session_factory
from nostalgiabox.persistence.runtime_sources import SqlAlchemyRuntimeDataSource
from nostalgiabox.playback.fake import FakePlayer
from nostalgiabox.seed.manifest import SeedManifest
from nostalgiabox.seed.service import seed_manifest
from tests.support.clock import FakeClock

_BACKEND_ROOT = Path(__file__).parents[2]
_PHASE2_REVISION = "20260808_0001"


def test_populated_phase2_upgrade_downgrade_reupgrade_preserves_rows_and_runtime(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'populated.db'}"
    monkeypatch.setenv("NOSTALGIABOX_DATABASE_URL", database_url)
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    command.upgrade(config, _PHASE2_REVISION)
    _seed_phase2(database_url)
    before = _phase2_rows(database_url)
    before_foreign_keys = _timeline_foreign_keys(database_url)

    command.upgrade(config, "head")

    assert _catalogue_ids(database_url) == ("media-a", "media-b", "media-c")
    assert _phase2_rows(database_url) == before
    assert _timeline_foreign_keys(database_url) == before_foreign_keys
    _assert_phase2_runtime_unchanged(database_url)

    command.downgrade(config, _PHASE2_REVISION)

    assert not {
        "catalogue_items",
        "media_sources",
        "media_files",
        "playable_renditions",
    }.intersection(_table_names(database_url))
    assert _phase2_rows(database_url) == before
    assert _timeline_foreign_keys(database_url) == before_foreign_keys

    command.upgrade(config, "head")

    assert _catalogue_ids(database_url) == ("media-a", "media-b", "media-c")
    assert _phase2_rows(database_url) == before


def test_migration_rejects_invalid_legacy_id_before_creating_catalogue_tables(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'invalid.db'}"
    monkeypatch.setenv("NOSTALGIABOX_DATABASE_URL", database_url)
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    command.upgrade(config, _PHASE2_REVISION)
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO media_items (id, title, duration_us, path) "
                    "VALUES (' ', 'Invalid', 1, '/invalid.mkv')"
                )
            )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="blank legacy"):
        command.upgrade(config, "head")

    assert "catalogue_items" not in _table_names(database_url)
    assert _phase2_rows(database_url)["media_items"] == ((" ", "Invalid", 1, "/invalid.mkv"),)


def _seed_phase2(database_url: str) -> None:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        factory = create_session_factory(engine)
        with factory.begin() as session:
            seed_manifest(
                session,
                SeedManifest.model_validate(
                    {
                        "channel": {"id": "channel-1", "number": 1, "name": "One"},
                        "start_utc": "2026-08-09T12:00:00Z",
                        "media": [
                            {
                                "id": f"media-{suffix}",
                                "title": f"Programme {suffix}",
                                "duration_us": 600_000_000,
                                "path": f"/phase2/media-{suffix}.mkv",
                            }
                            for suffix in ("a", "b", "c")
                        ],
                    }
                ),
            )
    finally:
        engine.dispose()


def _phase2_rows(database_url: str) -> dict[str, tuple[tuple[object, ...], ...]]:
    queries = {
        "media_items": "SELECT id, title, duration_us, path FROM media_items ORDER BY id",
        "channels": "SELECT id, number, name FROM channels ORDER BY id",
        "timeline_entries": (
            "SELECT id, channel_id, media_item_id, content_kind, start_utc_us, end_utc_us "
            "FROM timeline_entries ORDER BY id"
        ),
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


def _catalogue_ids(database_url: str) -> tuple[str, ...]:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        with engine.connect() as connection:
            return tuple(connection.scalars(text("SELECT id FROM catalogue_items ORDER BY id")))
    finally:
        engine.dispose()


def _assert_phase2_runtime_unchanged(database_url: str) -> None:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        source = SqlAlchemyRuntimeDataSource(create_session_factory(engine))
        player = FakePlayer()
        runtime = ChannelRuntime(
            FakeClock(datetime(2026, 8, 9, 12, 12, 30, 123456, tzinfo=UTC)),
            source,
            source,
            player,
        )
        snapshot = runtime.synchronise(source.get_by_number(1).id)
        assert snapshot.media_item_id.value == "media-b"
        assert snapshot.live_offset == timedelta(minutes=2, seconds=30, microseconds=123456)
        assert player.loaded_path == "/phase2/media-b.mkv"
    finally:
        engine.dispose()


def _table_names(database_url: str) -> set[str]:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _timeline_foreign_keys(database_url: str) -> set[tuple[str, tuple[str, ...], tuple[str, ...]]]:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        return {
            (
                foreign_key["referred_table"],
                tuple(foreign_key["constrained_columns"]),
                tuple(foreign_key["referred_columns"]),
            )
            for foreign_key in inspect(engine).get_foreign_keys("timeline_entries")
        }
    finally:
        engine.dispose()
