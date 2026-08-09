"""Tests for explicit, resource-safe input proof composition."""

from collections.abc import Iterator

import pytest

from nostalgiabox.application.input import ApplicationInputController, InputAction
from nostalgiabox.input import cli
from nostalgiabox.input.cli import build_parser, run_input_loop
from nostalgiabox.input.linux import LinuxInputSource, RawInputEvent
from nostalgiabox.input.profile import NORDIC_1915_1025_CONSUMER
from nostalgiabox.playback.fake import FakePlayer


class InterruptingDevice:
    def read_loop(self) -> Iterator[RawInputEvent]:
        raise KeyboardInterrupt
        yield

    def close(self) -> None:
        pass


class ClosingSource:
    profile = NORDIC_1915_1025_CONSUMER

    def __init__(self, *_: object, **__: object) -> None:
        self.closed = False

    def actions(self) -> Iterator[InputAction]:
        yield InputAction.PLAY_PAUSE
        raise KeyboardInterrupt

    def close(self) -> None:
        self.closed = True


def test_input_proof_requires_explicit_device_and_socket() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_input_loop_reports_clean_keyboard_interrupt() -> None:
    source = LinuxInputSource(
        "/operator/stable-input-path",
        NORDIC_1915_1025_CONSUMER,
        device_factory=lambda _: InterruptingDevice(),
    )
    reports: list[str] = []

    run_input_loop(source, ApplicationInputController(FakePlayer()), report=reports.append)

    assert reports == ["Input proof stopped."]


def test_main_closes_player_and_input_source(monkeypatch: pytest.MonkeyPatch) -> None:
    player = FakePlayer()
    player.load("/proof/media.mkv")
    source = ClosingSource()
    monkeypatch.setattr(cli, "_connect_player", lambda *_: player)
    monkeypatch.setattr(cli, "LinuxInputSource", lambda *_: source)

    result = cli.main(["--device", "/operator/stable-input-path", "--socket", "/tmp/x.sock"])

    assert result == 0
    assert source.closed
    assert player.history[-1].operation == "close"
