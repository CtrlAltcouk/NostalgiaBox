"""Deterministic tests for authoritative one-channel runtime orchestration."""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from nostalgiabox.application.player import PlayerUnavailableError
from nostalgiabox.application.runtime import (
    ChannelRuntime,
    ChannelUnavailableError,
    MediaLocationUnavailableError,
    RuntimeAction,
    RuntimeNotActiveError,
    RuntimeTimelineNotCoveredError,
)
from nostalgiabox.config.logging import JsonFormatter
from nostalgiabox.domain.models import Channel, ChannelId, MediaItem, MediaItemId
from nostalgiabox.domain.timeline import ChannelTimeline, build_sequential_timeline
from nostalgiabox.playback.fake import FakePlayer

from ...support.clock import FakeClock

START = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


@dataclass
class FakeTimelineSource:
    timeline: ChannelTimeline
    loads: list[ChannelId] = field(default_factory=list)

    def load(self, channel_id: ChannelId) -> ChannelTimeline:
        self.loads.append(channel_id)
        return self.timeline


@dataclass
class FakeMediaLocationSource:
    paths: dict[MediaItemId, str]
    lookups: list[MediaItemId] = field(default_factory=list)

    def get_path(self, media_item_id: MediaItemId) -> str:
        self.lookups.append(media_item_id)
        try:
            return self.paths[media_item_id]
        except KeyError as error:
            raise MediaLocationUnavailableError(
                f"media {media_item_id.value!r} has no location"
            ) from error


class UnavailableTimelineSource:
    def load(self, channel_id: ChannelId) -> ChannelTimeline:
        raise ChannelUnavailableError(f"channel {channel_id.value!r} is unavailable")


def test_initial_tune_exactly_at_programme_start_loads_offset_zero() -> None:
    runtime, player, _, _ = _runtime(START)

    snapshot = runtime.synchronise(ChannelId("channel-001"))

    assert snapshot.timeline_entry_id.value.endswith(":0")
    assert snapshot.live_offset == timedelta()
    assert player.history[0].path == "/proof/media-a.mkv"
    assert player.history[0].position == timedelta()


def test_initial_tune_mid_programme_loads_exact_live_offset() -> None:
    runtime, player, _, _ = _runtime(START + timedelta(minutes=4, microseconds=123))

    snapshot = runtime.synchronise(ChannelId("channel-001"))

    expected = timedelta(minutes=4, microseconds=123)
    assert snapshot.live_offset == expected
    assert player.history[0].position == expected


def test_one_microsecond_before_boundary_remains_current_entry() -> None:
    runtime, player, _, _ = _runtime(START + timedelta(minutes=10, microseconds=-1))

    snapshot = runtime.synchronise(ChannelId("channel-001"))

    assert snapshot.media_item_id == MediaItemId("media-a")
    assert player.history[0].position == timedelta(minutes=10, microseconds=-1)


def test_exact_boundary_loads_next_entry_at_zero() -> None:
    runtime, player, _, _ = _runtime(START + timedelta(minutes=10))

    snapshot = runtime.synchronise(ChannelId("channel-001"))

    assert snapshot.media_item_id == MediaItemId("media-b")
    assert snapshot.live_offset == timedelta()
    assert player.history[0].path == "/proof/media-b.mkv"


def test_tick_within_same_entry_does_not_reload_player() -> None:
    runtime, player, clock, _ = _runtime(START + timedelta(minutes=1))
    runtime.synchronise(ChannelId("channel-001"))
    clock.advance(timedelta(minutes=2))

    snapshot = runtime.tick()

    assert snapshot.last_action is RuntimeAction.NO_CHANGE
    assert snapshot.live_offset == timedelta(minutes=3)
    assert [call.operation for call in player.history] == ["load"]


def test_crossing_boundary_loads_next_media_exactly_once() -> None:
    runtime, player, clock, _ = _runtime(START + timedelta(minutes=9))
    runtime.synchronise(ChannelId("channel-001"))
    clock.advance(timedelta(minutes=1, seconds=30))

    snapshot = runtime.tick()

    assert snapshot.last_action is RuntimeAction.BOUNDARY_ADVANCE
    assert snapshot.media_item_id == MediaItemId("media-b")
    assert player.history[-1].position == timedelta(seconds=30)
    assert [call.operation for call in player.history] == ["load", "load"]


def test_multiple_successive_boundaries_follow_fake_clock() -> None:
    runtime, player, clock, _ = _runtime(START)
    runtime.synchronise(ChannelId("channel-001"))

    for _ in range(2):
        clock.advance(timedelta(minutes=10))
        runtime.tick()

    assert [call.path for call in player.history] == [
        "/proof/media-a.mkv",
        "/proof/media-b.mkv",
        "/proof/media-c.mkv",
    ]
    assert all(call.position == timedelta() for call in player.history)


def test_fresh_runtime_rejoins_mid_programme_without_prior_state() -> None:
    runtime, player, _, _ = _runtime(START + timedelta(minutes=14, seconds=20))

    snapshot = runtime.synchronise(ChannelId("channel-001"))

    assert snapshot.media_item_id == MediaItemId("media-b")
    assert player.history[0].position == timedelta(minutes=4, seconds=20)


def test_fresh_runtime_after_later_boundary_uses_current_programme() -> None:
    runtime, player, _, _ = _runtime(START + timedelta(minutes=22))

    snapshot = runtime.synchronise(ChannelId("channel-001"))

    assert snapshot.media_item_id == MediaItemId("media-c")
    assert player.history[0].position == timedelta(minutes=2)


def test_forced_resync_within_same_entry_reloads_at_updated_offset() -> None:
    runtime, player, clock, timeline_source = _runtime(START + timedelta(minutes=1))
    runtime.synchronise(ChannelId("channel-001"))
    clock.advance(timedelta(minutes=5))

    snapshot = runtime.resynchronise()

    assert snapshot.last_action is RuntimeAction.FORCED_RESYNC
    assert player.history[-1].position == timedelta(minutes=6)
    assert len(player.history) == 2
    assert len(timeline_source.loads) == 2


def test_forced_resync_after_boundary_loads_new_programme_and_offset() -> None:
    runtime, player, clock, _ = _runtime(START + timedelta(minutes=2))
    runtime.synchronise(ChannelId("channel-001"))
    clock.advance(timedelta(minutes=10, seconds=15))

    snapshot = runtime.resynchronise()

    assert snapshot.media_item_id == MediaItemId("media-b")
    assert player.history[-1].position == timedelta(minutes=2, seconds=15)


def test_time_outside_timeline_is_explicit_and_does_not_load() -> None:
    runtime, player, _, _ = _runtime(START - timedelta(microseconds=1))

    with pytest.raises(RuntimeTimelineNotCoveredError) as raised:
        runtime.synchronise(ChannelId("channel-001"))

    assert isinstance(raised.value.__cause__, Exception)
    assert player.history == []


def test_unavailable_channel_timeline_is_explicit_and_does_not_load() -> None:
    player = FakePlayer()
    runtime = ChannelRuntime(
        FakeClock(START),
        UnavailableTimelineSource(),
        FakeMediaLocationSource({}),
        player,
    )

    with pytest.raises(ChannelUnavailableError, match="unavailable"):
        runtime.synchronise(ChannelId("missing-channel"))

    assert player.history == []


def test_missing_media_location_is_explicit_and_does_not_load() -> None:
    timeline = _timeline()
    player = FakePlayer()
    runtime = ChannelRuntime(
        FakeClock(START), FakeTimelineSource(timeline), FakeMediaLocationSource({}), player
    )

    with pytest.raises(MediaLocationUnavailableError, match="no location"):
        runtime.synchronise(timeline.channel.id)

    assert player.history == []


def test_player_failure_remains_typed_and_observable() -> None:
    runtime, player, _, _ = _runtime(START)
    player.fail_next(PlayerUnavailableError("MPV unavailable"))

    with pytest.raises(PlayerUnavailableError, match="MPV unavailable"):
        runtime.synchronise(ChannelId("channel-001"))

    assert runtime.get_snapshot() is None


def test_runtime_snapshot_contains_exact_diagnostic_values() -> None:
    now = START + timedelta(minutes=12, microseconds=345)
    runtime, _, _, _ = _runtime(now)

    snapshot = runtime.synchronise(ChannelId("channel-001"))

    assert snapshot.channel_id == ChannelId("channel-001")
    assert snapshot.channel_number == 1
    assert snapshot.channel_name == "Channel 001"
    assert snapshot.timeline_entry_id.value.endswith(":1")
    assert snapshot.media_item_id == MediaItemId("media-b")
    assert snapshot.now_utc == now
    assert snapshot.entry_start_utc == START + timedelta(minutes=10)
    assert snapshot.entry_end_utc == START + timedelta(minutes=20)
    assert snapshot.live_offset == timedelta(minutes=2, microseconds=345)
    assert snapshot.last_action is RuntimeAction.INITIAL_TUNE


def test_successful_load_log_contains_structured_context() -> None:
    runtime, _, _, _ = _runtime(START + timedelta(seconds=7))
    records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    runtime_logger = logging.getLogger("nostalgiabox.application.runtime")
    handler = CaptureHandler()
    previous_level = runtime_logger.level
    previous_disabled = runtime_logger.disabled
    runtime_logger.addHandler(handler)
    runtime_logger.setLevel(logging.INFO)
    runtime_logger.disabled = False
    try:
        runtime.synchronise(ChannelId("channel-001"))
    finally:
        runtime_logger.removeHandler(handler)
        runtime_logger.setLevel(previous_level)
        runtime_logger.disabled = previous_disabled

    record = records[-1]
    assert record.__dict__["action"] == "initial_tune"
    assert record.__dict__["channel_id"] == "channel-001"
    assert str(record.__dict__["timeline_entry_id"]).endswith(":0")
    assert record.__dict__["media_item_id"] == "media-a"
    assert record.__dict__["now_utc"] == "2026-08-08T12:00:07+00:00"
    assert record.__dict__["entry_start_utc"] == "2026-08-08T12:00:00+00:00"
    assert record.__dict__["entry_end_utc"] == "2026-08-08T12:10:00+00:00"
    assert record.__dict__["target_live_offset_us"] == 7_000_000
    payload = json.loads(JsonFormatter().format(record))
    assert payload["action"] == "initial_tune"
    assert payload["target_live_offset_us"] == 7_000_000


@pytest.mark.parametrize("operation", ["tick", "resynchronise"])
def test_tick_and_resync_require_initial_synchronisation(operation: str) -> None:
    runtime, _, _, _ = _runtime(START)

    with pytest.raises(RuntimeNotActiveError):
        getattr(runtime, operation)()


def _runtime(
    now: datetime,
) -> tuple[ChannelRuntime, FakePlayer, FakeClock, FakeTimelineSource]:
    timeline = _timeline()
    timeline_source = FakeTimelineSource(timeline)
    media_source = FakeMediaLocationSource(
        {
            MediaItemId("media-a"): "/proof/media-a.mkv",
            MediaItemId("media-b"): "/proof/media-b.mkv",
            MediaItemId("media-c"): "/proof/media-c.mkv",
        }
    )
    player = FakePlayer()
    clock = FakeClock(now)
    return (
        ChannelRuntime(clock, timeline_source, media_source, player),
        player,
        clock,
        timeline_source,
    )


def _timeline() -> ChannelTimeline:
    channel = Channel(ChannelId("channel-001"), 1, "Channel 001")
    media = tuple(
        MediaItem(MediaItemId(f"media-{suffix}"), f"Programme {suffix}", timedelta(minutes=10))
        for suffix in ("a", "b", "c")
    )
    return build_sequential_timeline(channel, START, media)
