"""Deterministic tests for Linux event translation and profile isolation."""

import inspect
from dataclasses import dataclass

from nostalgiabox.application.input import InputAction
from nostalgiabox.input import linux
from nostalgiabox.input.linux import LinuxInputSource, translate_event
from nostalgiabox.input.profile import NORDIC_1915_1025_CONSUMER, RemoteProfile


@dataclass(frozen=True)
class Event:
    type: int
    code: int
    value: int


class Device:
    def __init__(self, events: list[Event]) -> None:
        self.events = events
        self.closed = False

    def read_loop(self):  # type: ignore[no-untyped-def]
        yield from self.events

    def close(self) -> None:
        self.closed = True


def test_raw_playpause_press_maps_exactly_once() -> None:
    device = Device(
        [
            Event(1, 164, 1),
            Event(1, 164, 2),
            Event(1, 164, 0),
        ]
    )
    source = LinuxInputSource(
        "/operator/stable-input-path",
        NORDIC_1915_1025_CONSUMER,
        device_factory=lambda _: device,
    )

    assert list(source.actions()) == [InputAction.PLAY_PAUSE]


def test_release_and_repeat_produce_no_action() -> None:
    assert translate_event(Event(1, 164, 0), NORDIC_1915_1025_CONSUMER) is None
    assert translate_event(Event(1, 164, 2), NORDIC_1915_1025_CONSUMER) is None


def test_unknown_key_and_non_key_event_are_ignored() -> None:
    assert translate_event(Event(1, 999, 1), NORDIC_1915_1025_CONSUMER) is None
    assert translate_event(Event(2, 164, 1), NORDIC_1915_1025_CONSUMER) is None


def test_profile_remapping_changes_binding_without_controller_change() -> None:
    remapped = RemoteProfile("test-remap", {42: InputAction.PLAY_PAUSE})

    assert translate_event(Event(1, 164, 1), remapped) is None
    assert translate_event(Event(1, 42, 1), remapped) is InputAction.PLAY_PAUSE


def test_source_closes_injected_device() -> None:
    device = Device([])
    source = LinuxInputSource(
        "/operator/stable-input-path",
        NORDIC_1915_1025_CONSUMER,
        device_factory=lambda _: device,
    )

    source.close()

    assert device.closed


def test_linux_adapter_has_no_timeline_persistence_or_mpv_dependency() -> None:
    source = inspect.getsource(linux).lower()

    assert "timeline" not in source
    assert "sqlalchemy" not in source
    assert "nostalgiabox.playback" not in source
    assert "mpv" not in source


def test_no_unstable_event_device_path_is_hard_coded() -> None:
    assert "/dev/input/event" not in inspect.getsource(linux)
