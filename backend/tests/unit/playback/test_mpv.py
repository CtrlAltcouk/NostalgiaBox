"""Tests for MPV command mapping and position conversion."""

from collections.abc import Callable
from datetime import timedelta

import pytest

from nostalgiabox.application.player import PlayerMediaLoadError, PlayerProtocolError, PlayerState
from nostalgiabox.playback.mpv import (
    MpvPlayer,
    mpv_seconds_to_timedelta,
    timedelta_to_mpv_seconds,
)
from nostalgiabox.playback.transport import JsonValue, MpvEvent


class FakeCommandTransport:
    def __init__(
        self,
        responses: list[JsonValue] | None = None,
        events: list[MpvEvent] | None = None,
    ) -> None:
        self.commands: list[list[JsonValue]] = []
        self.responses = list(responses or [])
        self.events = list(
            events
            or [
                MpvEvent("start-file", {"playlist_entry_id": 17}),
                MpvEvent("file-loaded", {}),
            ]
        )
        self.closed = False

    def command(self, command: list[JsonValue]) -> JsonValue:
        self.commands.append(command)
        return self.responses.pop(0) if self.responses else None

    def drain_events(self) -> tuple[MpvEvent, ...]:
        return ()

    def wait_for_event(self, predicate: Callable[[MpvEvent], bool]) -> MpvEvent:
        for index, event in enumerate(self.events):
            if predicate(event):
                return self.events.pop(index)
        raise AssertionError("no scripted MPV event matched")

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize(
    ("position", "seconds"),
    [
        (timedelta(), 0.0),
        (timedelta(microseconds=1), 0.000001),
        (timedelta(hours=1, seconds=2, microseconds=345_678), 3602.345678),
    ],
)
def test_timedelta_to_mpv_seconds(position: timedelta, seconds: float) -> None:
    assert timedelta_to_mpv_seconds(position) == seconds


def test_timedelta_to_mpv_seconds_rejects_negative_position() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        timedelta_to_mpv_seconds(timedelta(microseconds=-1))


@pytest.mark.parametrize(
    ("seconds", "position"),
    [
        (0, timedelta()),
        (1e-6, timedelta(microseconds=1)),
        (62.345678, timedelta(minutes=1, seconds=2, microseconds=345_678)),
        (0.1234567, timedelta(microseconds=123_457)),
    ],
)
def test_mpv_seconds_to_timedelta(seconds: int | float, position: timedelta) -> None:
    assert mpv_seconds_to_timedelta(seconds) == position


@pytest.mark.parametrize("value", [None, True, "1", -0.1, float("inf"), float("nan")])
def test_mpv_seconds_to_timedelta_rejects_invalid_data(value: object) -> None:
    with pytest.raises(ValueError):
        mpv_seconds_to_timedelta(value)


def test_load_at_position_uses_structured_loadfile_options() -> None:
    transport = FakeCommandTransport()
    player = MpvPlayer(transport)
    awkward_path = "/media/It's & [odd] — 日本語 programme.mkv"

    player.load(awkward_path, timedelta(seconds=12, microseconds=345_678))

    assert transport.commands == [["loadfile", awkward_path, "replace", -1, {"start": "12.345678"}]]


def test_load_waits_for_matching_structured_success_event() -> None:
    transport = FakeCommandTransport(
        events=[
            MpvEvent("end-file", {"playlist_entry_id": 4, "reason": "stop"}),
            MpvEvent("start-file", {"playlist_entry_id": 5}),
            MpvEvent("file-loaded", {}),
        ]
    )

    MpvPlayer(transport).load("/proof/valid.mkv")

    assert [event.name for event in transport.events] == ["end-file"]


def test_load_error_event_becomes_typed_media_failure() -> None:
    transport = FakeCommandTransport(
        events=[
            MpvEvent("start-file", {"playlist_entry_id": 8}),
            MpvEvent(
                "end-file",
                {
                    "playlist_entry_id": 8,
                    "reason": "error",
                    "file_error": "loading failed",
                },
            ),
        ]
    )

    with pytest.raises(PlayerMediaLoadError, match="loading failed") as raised:
        MpvPlayer(transport).load("/proof/corrupt.bin")

    assert raised.value.player_error == "loading failed"


def test_load_rejects_malformed_start_event() -> None:
    transport = FakeCommandTransport(events=[MpvEvent("start-file", {})])

    with pytest.raises(PlayerProtocolError, match="playlist_entry_id"):
        MpvPlayer(transport).load("/proof/media.mkv")


def test_seek_uses_absolute_exact_semantics() -> None:
    transport = FakeCommandTransport()
    player = MpvPlayer(transport)

    player.seek(timedelta(seconds=17, microseconds=500_000))

    assert transport.commands == [["seek", 17.5, "absolute+exact"]]


def test_pause_and_resume_use_pause_property() -> None:
    transport = FakeCommandTransport()
    player = MpvPlayer(transport)

    player.pause()
    player.resume()

    assert transport.commands == [
        ["set_property", "pause", True],
        ["set_property", "pause", False],
    ]


def test_stop_uses_mpv_stop_command() -> None:
    transport = FakeCommandTransport()
    MpvPlayer(transport).stop()

    assert transport.commands == [["stop"]]


def test_valid_time_position_returns_timedelta() -> None:
    transport = FakeCommandTransport([False, 61.234567])

    position = MpvPlayer(transport).get_position()

    assert position == timedelta(minutes=1, seconds=1, microseconds=234_567)
    assert transport.commands == [
        ["get_property", "idle-active"],
        ["get_property", "time-pos"],
    ]


def test_idle_position_is_none_without_fabricating_zero() -> None:
    transport = FakeCommandTransport([True])

    assert MpvPlayer(transport).get_position() is None
    assert transport.commands == [["get_property", "idle-active"]]


def test_invalid_time_position_is_protocol_error() -> None:
    transport = FakeCommandTransport([False, "not numeric"])

    with pytest.raises(PlayerProtocolError, match="invalid time-pos"):
        MpvPlayer(transport).get_position()


@pytest.mark.parametrize(
    ("responses", "expected"),
    [
        ([True], PlayerState.IDLE),
        ([False, False], PlayerState.PLAYING),
        ([False, True], PlayerState.PAUSED),
    ],
)
def test_player_state_mapping(responses: list[JsonValue], expected: PlayerState) -> None:
    assert MpvPlayer(FakeCommandTransport(responses)).get_state() is expected


def test_invalid_state_property_is_protocol_error() -> None:
    with pytest.raises(PlayerProtocolError, match="invalid idle-active"):
        MpvPlayer(FakeCommandTransport([0])).get_state()


def test_health_queries_responsive_mpv_property() -> None:
    transport = FakeCommandTransport(["0.41.0"])

    MpvPlayer(transport).check_health()

    assert transport.commands == [["get_property", "mpv-version"]]


def test_health_rejects_invalid_response() -> None:
    with pytest.raises(PlayerProtocolError, match="invalid mpv-version"):
        MpvPlayer(FakeCommandTransport([None])).check_health()


def test_close_releases_transport() -> None:
    transport = FakeCommandTransport()
    MpvPlayer(transport).close()

    assert transport.closed
