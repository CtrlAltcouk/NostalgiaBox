"""Task 3.2 migration compatibility and lossless lifecycle tests."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from pytest import MonkeyPatch
from sqlalchemy import text

from nostalgiabox.config.settings import Settings
from nostalgiabox.domain.catalogue import MediaSource, MediaSourceId, SourceAvailability
from nostalgiabox.persistence.catalogue_repositories import SqlAlchemyMediaSourceRepository
from nostalgiabox.persistence.database import create_engine, create_session_factory

_BACKEND_ROOT = Path(__file__).parents[2]
_TASK31_REVISION = "20260809_0002"


def test_populated_task31_upgrade_downgrade_reupgrade_is_lossless(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'source-migration.db'}"
    monkeypatch.setenv("NOSTALGIABOX_DATABASE_URL", database_url)
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    command.upgrade(config, _TASK31_REVISION)
    _seed_task31(database_url)
    before = _foundation_rows(database_url)

    command.upgrade(config, "head")

    assert _foundation_rows(database_url) == before
    source = _load_source(database_url, "source-existing")
    assert source.display_name == "source-existing"
    assert source.configured_root is None
    assert source.enabled is False
    assert source.availability is SourceAvailability.UNKNOWN
    assert source.last_checked_utc is None
    assert source.last_successful_scan_utc is None
    assert source.current_error_code is None
    assert source.retired_utc is None
    assert source.revision == 1
    smb = _load_source(database_url, "source-smb")
    assert smb.display_name == "source-smb"
    assert smb.configured_root is None
    assert smb.enabled is False
    assert smb.availability is SourceAvailability.UNKNOWN

    command.downgrade(config, _TASK31_REVISION)

    assert _foundation_rows(database_url) == before

    command.upgrade(config, "head")

    assert _foundation_rows(database_url) == before
    assert _load_source(database_url, "source-existing").configured_root is None


def _seed_task31(database_url: str) -> None:
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
            connection.execute(text("INSERT INTO catalogue_items VALUES ('legacy-media')"))
            connection.execute(
                text("INSERT INTO media_sources VALUES ('source-existing', 'local')")
            )
            connection.execute(text("INSERT INTO media_sources VALUES ('source-smb', 'smb')"))
            connection.execute(
                text(
                    "INSERT INTO media_files VALUES "
                    "('file-1', 'source-existing', 'legacy/media.mkv', 'legacy/media.mkv')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO playable_renditions VALUES "
                    "('rendition-1', 'legacy-media', 'file-1', 0, 60000000, 60000000, 1, 1)"
                )
            )
    finally:
        engine.dispose()


def _foundation_rows(database_url: str) -> dict[str, tuple[tuple[object, ...], ...]]:
    queries = {
        "media_items": "SELECT id, title, duration_us, path FROM media_items ORDER BY id",
        "channels": "SELECT id, number, name FROM channels ORDER BY id",
        "timeline_entries": (
            "SELECT id, channel_id, media_item_id, content_kind, start_utc_us, end_utc_us "
            "FROM timeline_entries ORDER BY id"
        ),
        "catalogue_items": "SELECT id FROM catalogue_items ORDER BY id",
        "media_sources": "SELECT id, kind FROM media_sources ORDER BY id",
        "media_files": (
            "SELECT id, source_id, normalized_relative_locator, original_relative_locator "
            "FROM media_files ORDER BY id"
        ),
        "playable_renditions": (
            "SELECT id, catalogue_item_id, media_file_id, segment_start_us, "
            "segment_duration_us, logical_playable_duration_us, is_whole_file, preferred "
            "FROM playable_renditions ORDER BY id"
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


def _load_source(database_url: str, source_id: str) -> MediaSource:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        with create_session_factory(engine)() as session:
            source = SqlAlchemyMediaSourceRepository(session).get_by_id(MediaSourceId(source_id))
            assert source is not None
            return source
    finally:
        engine.dispose()
