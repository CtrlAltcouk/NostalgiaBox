"""SQLite-to-application one-channel proof using FakeClock and FakePlayer."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from pytest import MonkeyPatch

from nostalgiabox.application.runtime import ChannelRuntime
from nostalgiabox.config.settings import Settings
from nostalgiabox.persistence.database import create_engine, create_session_factory
from nostalgiabox.persistence.runtime_sources import (
    SqlAlchemyRuntimeDataSource,
    ensure_runtime_schema,
)
from nostalgiabox.playback.fake import FakePlayer
from nostalgiabox.seed.manifest import SeedManifest
from nostalgiabox.seed.service import seed_manifest

from ..support.clock import FakeClock

_BACKEND_ROOT = Path(__file__).parents[2]


def test_migrated_sqlite_runtime_loads_seeded_path_at_wall_clock_offset(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'channel-proof.db'}"
    monkeypatch.setenv("NOSTALGIABOX_DATABASE_URL", database_url)
    command.upgrade(Config(str(_BACKEND_ROOT / "alembic.ini")), "head")

    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        ensure_runtime_schema(engine)
        session_factory = create_session_factory(engine)
        with session_factory.begin() as session:
            seed_manifest(session, _manifest())

        source = SqlAlchemyRuntimeDataSource(session_factory)
        channel = source.get_by_number(1)
        player = FakePlayer()
        clock = FakeClock(datetime(2026, 8, 8, 12, 12, 30, 123456, tzinfo=UTC))
        runtime = ChannelRuntime(clock, source, source, player)

        snapshot = runtime.synchronise(channel.id)

        assert channel.name == "Channel 001"
        assert snapshot.media_item_id.value == "media-b"
        assert snapshot.live_offset == timedelta(minutes=2, seconds=30, microseconds=123456)
        assert player.history[0].path == "/proof/media-b.mkv"
        assert player.history[0].position == snapshot.live_offset
    finally:
        engine.dispose()


def _manifest() -> SeedManifest:
    return SeedManifest.model_validate(
        {
            "channel": {"id": "channel-001", "number": 1, "name": "Channel 001"},
            "start_utc": "2026-08-08T12:00:00Z",
            "media": [
                {
                    "id": f"media-{suffix}",
                    "title": f"Programme {suffix}",
                    "duration_us": 600_000_000,
                    "path": f"/proof/media-{suffix}.mkv",
                }
                for suffix in ("a", "b", "c")
            ],
        }
    )
