"""Tests for safe explicit one-channel proof command behaviour."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nostalgiabox.application.runtime import ChannelRuntime
from nostalgiabox.config.settings import Settings
from nostalgiabox.domain.models import Channel, ChannelId, MediaItem, MediaItemId
from nostalgiabox.domain.timeline import ChannelTimeline, build_sequential_timeline
from nostalgiabox.persistence import models as persistence_models
from nostalgiabox.persistence.database import create_engine, create_session_factory
from nostalgiabox.playback.fake import FakePlayer
from nostalgiabox.proof import cli
from nostalgiabox.proof.cli import (
    ProofConfigurationError,
    build_parser,
    run_proof_loop,
    validate_proof_database_url,
)
from nostalgiabox.seed.manifest import SeedManifest
from nostalgiabox.seed.service import seed_manifest

from ...support.clock import FakeClock


class TimelineSource:
    def __init__(self, timeline: ChannelTimeline) -> None:
        self.timeline = timeline

    def load(self, channel_id: ChannelId) -> ChannelTimeline:
        assert channel_id == self.timeline.channel.id
        return self.timeline


class MediaSource:
    def get_path(self, media_item_id: MediaItemId) -> str:
        return f"/proof/{media_item_id.value}.mkv"


def test_proof_cli_requires_explicit_database_socket_and_channel() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


@pytest.mark.parametrize(
    "database_url",
    ["sqlite+pysqlite:///:memory:", "sqlite://", "sqlite:///file::memory:?cache=shared"],
)
def test_proof_cli_rejects_in_memory_database(database_url: str) -> None:
    with pytest.raises(ProofConfigurationError, match="persistent database URL"):
        validate_proof_database_url(database_url)


def test_proof_cli_rejects_non_sqlite_database() -> None:
    with pytest.raises(ProofConfigurationError, match="SQLite"):
        validate_proof_database_url("postgresql://localhost/nostalgiabox")


def test_once_performs_one_synchronisation_without_sleeping() -> None:
    runtime, player = _runtime()
    reports: list[str] = []

    snapshot = run_proof_loop(
        runtime,
        ChannelId("channel-001"),
        once=True,
        poll_seconds=1,
        sleep=lambda _: pytest.fail("--once must not sleep"),
        report=reports.append,
    )

    assert snapshot.live_offset == timedelta(minutes=3)
    assert [call.operation for call in player.history] == ["load"]
    assert len(reports) == 1
    assert '"live_offset_us":180000000' in reports[0]


def test_continuous_loop_stops_cleanly_on_keyboard_interrupt() -> None:
    runtime, _ = _runtime()
    reports: list[str] = []

    snapshot = run_proof_loop(
        runtime,
        ChannelId("channel-001"),
        once=False,
        poll_seconds=1,
        sleep=lambda _: (_ for _ in ()).throw(KeyboardInterrupt),
        report=reports.append,
    )

    assert snapshot.live_offset == timedelta(minutes=3)
    assert reports[-1] == "Channel proof stopped."


def test_once_composition_closes_player_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'once-proof.db'}"
    engine = create_engine(Settings(environment="test", database_url=database_url))
    persistence_models.Base.metadata.create_all(engine)
    with create_session_factory(engine).begin() as session:
        seed_manifest(session, _manifest())
    engine.dispose()

    player = FakePlayer()
    monkeypatch.setattr(
        cli,
        "SystemClock",
        lambda: FakeClock(datetime(2026, 8, 8, 12, 3, tzinfo=UTC)),
    )
    monkeypatch.setattr(cli, "_connect_player", lambda *_: player)

    result = cli.main(
        [
            "--database-url",
            database_url,
            "--socket",
            str(tmp_path / "explicit.sock"),
            "--channel-number",
            "1",
            "--once",
        ]
    )

    assert result == 0
    assert [call.operation for call in player.history] == ["load", "close"]


def _runtime() -> tuple[ChannelRuntime, FakePlayer]:
    channel = Channel(ChannelId("channel-001"), 1, "Channel 001")
    media = MediaItem(MediaItemId("media-a"), "Programme A", timedelta(minutes=10))
    timeline = build_sequential_timeline(channel, datetime(2026, 8, 8, 12, tzinfo=UTC), [media])
    player = FakePlayer()
    runtime = ChannelRuntime(
        FakeClock(datetime(2026, 8, 8, 12, 3, tzinfo=UTC)),
        TimelineSource(timeline),
        MediaSource(),
        player,
    )
    return runtime, player


def _manifest() -> SeedManifest:
    return SeedManifest.model_validate(
        {
            "channel": {"id": "channel-001", "number": 1, "name": "Channel 001"},
            "start_utc": "2026-08-08T12:00:00Z",
            "media": [
                {
                    "id": "media-a",
                    "title": "Programme A",
                    "duration_us": 600_000_000,
                    "path": "/proof/media-a.mkv",
                }
            ],
        }
    )
