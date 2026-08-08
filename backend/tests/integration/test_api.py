"""API application smoke tests."""

import inspect
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from nostalgiabox.api import create_app
from nostalgiabox.api.routes import runtime as runtime_route
from nostalgiabox.application.runtime import RuntimeAction, RuntimeSnapshot
from nostalgiabox.config.settings import Settings
from nostalgiabox.domain.models import ChannelId, MediaItemId, TimelineEntryId


class SnapshotProvider:
    def __init__(self, snapshot: RuntimeSnapshot | None) -> None:
        self.snapshot = snapshot

    def get_snapshot(self) -> RuntimeSnapshot | None:
        return self.snapshot


def test_application_factory_creates_expected_routes() -> None:
    settings = Settings(environment="test", database_url="sqlite+pysqlite:///:memory:")
    app = create_app(settings)

    assert app.title == "NostalgiaBox Core API"
    assert app.state.settings is settings


def test_health_endpoint_returns_stable_response() -> None:
    app = create_app(Settings(environment="test", database_url="sqlite+pysqlite:///:memory:"))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"service": "nostalgiabox", "status": "ok"}


def test_runtime_endpoint_before_tune_is_explicitly_inactive() -> None:
    app = create_app(Settings(environment="test"))

    with TestClient(app) as client:
        response = client.get("/runtime")

    assert response.status_code == 200
    assert response.json() == {"active": False, "snapshot": None}


def test_runtime_endpoint_exposes_latest_snapshot_after_tune() -> None:
    provider = SnapshotProvider(_snapshot())
    app = create_app(Settings(environment="test"), provider)

    with TestClient(app) as client:
        response = client.get("/runtime")

    assert response.status_code == 200
    assert response.json() == {
        "active": True,
        "snapshot": {
            "channel_id": "channel-001",
            "channel_number": 1,
            "channel_name": "Channel 001",
            "timeline_entry_id": "entry-b",
            "media_item_id": "media-b",
            "now_utc": "2026-08-08T12:12:30.123456Z",
            "entry_start_utc": "2026-08-08T12:10:00Z",
            "entry_end_utc": "2026-08-08T12:20:00Z",
            "live_offset_us": 150_123_456,
            "last_action": "initial_tune",
        },
    }


def test_runtime_route_contains_no_scheduling_or_player_logic() -> None:
    source = inspect.getsource(runtime_route)

    assert "resolve_active_entry" not in source
    assert "Player.load" not in source
    assert "sqlalchemy" not in source.lower()
    assert "nostalgiabox.playback" not in source


def _snapshot() -> RuntimeSnapshot:
    return RuntimeSnapshot(
        channel_id=ChannelId("channel-001"),
        channel_number=1,
        channel_name="Channel 001",
        timeline_entry_id=TimelineEntryId("entry-b"),
        media_item_id=MediaItemId("media-b"),
        now_utc=datetime(2026, 8, 8, 12, 12, 30, 123456, tzinfo=UTC),
        entry_start_utc=datetime(2026, 8, 8, 12, 10, tzinfo=UTC),
        entry_end_utc=datetime(2026, 8, 8, 12, 20, tzinfo=UTC),
        live_offset=timedelta(minutes=2, seconds=30, microseconds=123456),
        last_action=RuntimeAction.INITIAL_TUNE,
    )
