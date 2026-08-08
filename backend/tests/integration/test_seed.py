"""Manifest, idempotency, isolation and transaction tests for proof seeding."""

from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

import pytest
from pydantic import ValidationError
from sqlalchemy import Engine, func, select

from nostalgiabox.domain import ChannelId, ChannelTimeline
from nostalgiabox.persistence.database import create_session_factory
from nostalgiabox.persistence.errors import SeedConflictError, SeedError, SeedSchemaMissingError
from nostalgiabox.persistence.models import ChannelRecord, MediaItemRecord, TimelineEntryRecord
from nostalgiabox.persistence.repositories import TimelineRepository
from nostalgiabox.seed.cli import seed_database
from nostalgiabox.seed.manifest import SeedManifest
from nostalgiabox.seed.service import ensure_seed_schema, seed_manifest


def test_manifest_builds_expected_channel_001_timeline(persistence_engine: Engine) -> None:
    session_factory = create_session_factory(persistence_engine)
    manifest = _manifest("channel-001", 1, "media-a", "media-b")

    with session_factory.begin() as session:
        expected = seed_manifest(session, manifest)

    with session_factory() as session:
        loaded = TimelineRepository(session).load(ChannelId("channel-001"))

    assert loaded == expected
    assert loaded.entries[0].start_utc == datetime(2026, 8, 8, 18, 0, tzinfo=UTC)
    assert loaded.entries[0].end_utc == datetime(2026, 8, 8, 18, 22, tzinfo=UTC)
    assert loaded.entries[1].end_utc == datetime(2026, 8, 8, 18, 47, tzinfo=UTC)


def test_same_manifest_twice_is_idempotent(persistence_engine: Engine) -> None:
    session_factory = create_session_factory(persistence_engine)
    manifest = _manifest("channel-001", 1, "media-a", "media-b")

    for _ in range(2):
        with session_factory.begin() as session:
            seed_manifest(session, manifest)

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ChannelRecord)) == 1
        assert session.scalar(select(func.count()).select_from(MediaItemRecord)) == 2
        assert session.scalar(select(func.count()).select_from(TimelineEntryRecord)) == 2


def test_replacement_affects_only_target_channel(persistence_engine: Engine) -> None:
    session_factory = create_session_factory(persistence_engine)
    channel_one = _manifest("channel-001", 1, "media-a", "media-b")
    channel_two = _manifest("channel-002", 2, "media-c", "media-d")

    with session_factory.begin() as session:
        seed_manifest(session, channel_one)
        seed_manifest(session, channel_two)
    replacement = _manifest("channel-001", 1, "media-a")
    with session_factory.begin() as session:
        seed_manifest(session, replacement)

    with session_factory() as session:
        channel_one_loaded = TimelineRepository(session).load(ChannelId("channel-001"))
        channel_two_loaded = TimelineRepository(session).load(ChannelId("channel-002"))

    assert len(channel_one_loaded.entries) == 1
    assert len(channel_two_loaded.entries) == 2


def test_failed_replacement_rolls_back_all_changes(
    persistence_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = create_session_factory(persistence_engine)
    original_manifest = _manifest("channel-001", 1, "media-a", "media-b")
    with session_factory.begin() as session:
        original_timeline = seed_manifest(session, original_manifest)

    original_replace = TimelineRepository.replace

    def replace_then_fail(self: TimelineRepository, timeline: ChannelTimeline) -> NoReturn:
        original_replace(self, timeline)
        raise RuntimeError("simulated transaction failure")

    monkeypatch.setattr(TimelineRepository, "replace", replace_then_fail)
    with pytest.raises(RuntimeError, match="simulated"), session_factory.begin() as session:
        seed_manifest(session, _manifest("channel-001", 1, "media-a"))

    with session_factory() as session:
        assert TimelineRepository(session).load(ChannelId("channel-001")) == original_timeline


def test_manifest_rejects_duplicate_media_ids() -> None:
    data = _manifest("channel-001", 1, "media-a").model_dump()
    data["media"] = [data["media"][0], data["media"][0]]

    with pytest.raises(ValidationError, match="media IDs must be unique"):
        SeedManifest.model_validate(data)


def test_seed_rejects_channel_number_owned_by_different_channel(
    persistence_engine: Engine,
) -> None:
    session_factory = create_session_factory(persistence_engine)
    with session_factory.begin() as session:
        seed_manifest(session, _manifest("channel-001", 1, "media-a"))

    with (
        pytest.raises(SeedConflictError, match="already belongs"),
        session_factory.begin() as session,
    ):
        seed_manifest(session, _manifest("different-channel", 1, "media-b"))


def test_seed_database_rejects_in_memory_target(tmp_path: Path) -> None:
    with pytest.raises(SeedError, match="persistent database URL"):
        seed_database("sqlite+pysqlite:///:memory:", tmp_path / "unused.json")


def test_seed_schema_check_requires_migration(tmp_path: Path) -> None:
    from nostalgiabox.config.settings import Settings
    from nostalgiabox.persistence.database import create_engine

    engine = create_engine(
        Settings(environment="test", database_url=f"sqlite+pysqlite:///{tmp_path / 'empty.db'}")
    )
    try:
        with pytest.raises(SeedSchemaMissingError, match="alembic upgrade head"):
            ensure_seed_schema(engine)
    finally:
        engine.dispose()


def _manifest(
    channel_id: str,
    channel_number: int,
    *media_ids: str,
) -> SeedManifest:
    return SeedManifest.model_validate(
        {
            "channel": {
                "id": channel_id,
                "number": channel_number,
                "name": f"Channel {channel_number:03d}",
            },
            "start_utc": "2026-08-08T18:00:00Z",
            "media": [
                {
                    "id": media_id,
                    "title": f"Programme {media_id}",
                    "duration_us": 1_320_000_000 if index == 0 else 1_500_000_000,
                    "path": f"/proof/{media_id}.mkv",
                }
                for index, media_id in enumerate(media_ids)
            ],
        }
    )
