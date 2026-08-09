"""Concise final integration proof across every implemented Phase 2 software layer."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from pytest import MonkeyPatch
from sqlalchemy import Engine

from nostalgiabox.application.player import PlayerMediaLoadError, PlayerUnavailableError
from nostalgiabox.application.runtime import (
    ChannelRuntime,
    RuntimeAction,
    RuntimeFailureCategory,
)
from nostalgiabox.config.settings import Settings
from nostalgiabox.persistence.database import create_engine, create_session_factory
from nostalgiabox.persistence.runtime_sources import SqlAlchemyRuntimeDataSource
from nostalgiabox.playback.fake import FakePlayer
from nostalgiabox.seed.manifest import SeedManifest
from nostalgiabox.seed.service import seed_manifest

from ..support.clock import FakeClock

_BACKEND_ROOT = Path(__file__).parents[2]
_START = datetime(2026, 8, 8, 12, tzinfo=UTC)


def test_migrated_channel_tune_boundary_restart_and_resynchronisation(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    engine, source = _migrated_source(tmp_path, monkeypatch, _manifest(_START))
    try:
        channel = source.get_by_number(1)
        clock = FakeClock(_START + timedelta(minutes=2))
        player = FakePlayer()
        runtime = ChannelRuntime(clock, source, source, player)

        initial = runtime.synchronise(channel.id)
        assert initial.media_item_id.value == "media-a"
        assert initial.live_offset == timedelta(minutes=2)
        assert player.history[-1].path == "/proof/media-a.mkv"
        assert player.history[-1].position == timedelta(minutes=2)

        clock.advance(timedelta(minutes=3))
        unchanged = runtime.tick()
        assert unchanged.last_action is RuntimeAction.NO_CHANGE
        assert [call.operation for call in player.history] == ["load"]

        clock.set(_START + timedelta(minutes=10))
        boundary = runtime.tick()
        assert boundary.media_item_id.value == "media-b"
        assert boundary.live_offset == timedelta()
        assert [call.operation for call in player.history] == ["load", "load"]

        player.seek(timedelta(minutes=9))
        clock.set(_START + timedelta(minutes=14, seconds=30))
        restarted = ChannelRuntime(clock, source, source, player)
        rejoined = restarted.synchronise(channel.id)
        assert rejoined.media_item_id.value == "media-b"
        assert rejoined.live_offset == timedelta(minutes=4, seconds=30)
        assert player.history[-1].position == rejoined.live_offset

        clock.advance(timedelta(minutes=1))
        same_entry = restarted.resynchronise()
        assert same_entry.last_action is RuntimeAction.FORCED_RESYNC
        assert same_entry.media_item_id.value == "media-b"
        assert same_entry.live_offset == timedelta(minutes=5, seconds=30)

        clock.set(_START + timedelta(minutes=21))
        crossed_boundary = restarted.resynchronise()
        assert crossed_boundary.media_item_id.value == "media-c"
        assert crossed_boundary.live_offset == timedelta(minutes=1)
        assert player.history[-1].path == "/proof/media-c.mkv"
    finally:
        engine.dispose()


def test_migrated_missing_media_and_player_loss_remain_distinct(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    engine, source = _migrated_source(tmp_path, monkeypatch, _manifest(_START))
    try:
        channel = source.get_by_number(1)
        clock = FakeClock(_START + timedelta(minutes=1))

        media_player = FakePlayer()
        media_player.fail_next(PlayerMediaLoadError("loading failed"))
        media_runtime = ChannelRuntime(clock, source, source, media_player)
        with pytest.raises(PlayerMediaLoadError):
            media_runtime.synchronise(channel.id)
        media_failure = media_runtime.get_failure()
        assert media_failure is not None
        assert media_failure.category is RuntimeFailureCategory.MEDIA_LOAD
        assert media_runtime.tick().last_action is RuntimeAction.MEDIA_RETRY_SUPPRESSED
        assert media_player.history == []

        unavailable_player = FakePlayer()
        unavailable_player.fail_next(PlayerUnavailableError("MPV unavailable"))
        unavailable_runtime = ChannelRuntime(clock, source, source, unavailable_player)
        with pytest.raises(PlayerUnavailableError):
            unavailable_runtime.synchronise(channel.id)
        unavailable_failure = unavailable_runtime.get_failure()
        assert unavailable_failure is not None
        assert unavailable_failure.category is RuntimeFailureCategory.PLAYER_UNAVAILABLE
        assert unavailable_failure.player_failure_type == "PlayerUnavailableError"
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("start_local", "clock_local", "expected_media", "expected_offset"),
    [
        (
            datetime(2026, 3, 29, 0, tzinfo=ZoneInfo("Europe/London")),
            datetime(2026, 3, 29, 2, 30, tzinfo=ZoneInfo("Europe/London")),
            "media-b",
            timedelta(minutes=30),
        ),
        (
            datetime(2026, 10, 25, 1, tzinfo=ZoneInfo("Europe/London"), fold=0),
            datetime(2026, 10, 25, 1, 30, tzinfo=ZoneInfo("Europe/London"), fold=1),
            "media-b",
            timedelta(minutes=30),
        ),
    ],
    ids=("spring-forward", "autumn-fold"),
)
def test_migrated_runtime_preserves_dst_absolute_instants(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    start_local: datetime,
    clock_local: datetime,
    expected_media: str,
    expected_offset: timedelta,
) -> None:
    engine, source = _migrated_source(
        tmp_path,
        monkeypatch,
        _manifest(start_local, duration=timedelta(hours=1)),
    )
    try:
        channel = source.get_by_number(1)
        player = FakePlayer()
        runtime = ChannelRuntime(FakeClock(clock_local), source, source, player)

        snapshot = runtime.synchronise(channel.id)

        assert snapshot.media_item_id.value == expected_media
        assert snapshot.live_offset == expected_offset
        assert snapshot.entry_start_utc.tzinfo is UTC
        assert snapshot.entry_end_utc.tzinfo is UTC
        assert snapshot.now_utc.tzinfo is UTC
        assert player.history[-1].position == expected_offset
    finally:
        engine.dispose()


def _migrated_source(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    manifest: SeedManifest,
) -> tuple[Engine, SqlAlchemyRuntimeDataSource]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'phase2-closure.db'}"
    monkeypatch.setenv("NOSTALGIABOX_DATABASE_URL", database_url)
    command.upgrade(Config(str(_BACKEND_ROOT / "alembic.ini")), "head")
    engine = create_engine(Settings(environment="test", database_url=database_url))
    session_factory = create_session_factory(engine)
    with session_factory.begin() as session:
        seed_manifest(session, manifest)
    return engine, SqlAlchemyRuntimeDataSource(session_factory)


def _manifest(start: datetime, *, duration: timedelta = timedelta(minutes=10)) -> SeedManifest:
    duration_us = int(duration.total_seconds() * 1_000_000)
    return SeedManifest.model_validate(
        {
            "channel": {"id": "channel-001", "number": 1, "name": "Channel 001"},
            "start_utc": start,
            "media": [
                {
                    "id": f"media-{suffix}",
                    "title": f"Programme {suffix}",
                    "duration_us": duration_us,
                    "path": f"/proof/media-{suffix}.mkv",
                }
                for suffix in ("a", "b", "c")
            ],
        }
    )
