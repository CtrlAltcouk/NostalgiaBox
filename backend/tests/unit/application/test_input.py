"""Tests for MPV-agnostic logical input dispatch."""

import inspect

from nostalgiabox.application import input as application_input
from nostalgiabox.application.input import ApplicationInputController, InputAction, InputOutcome
from nostalgiabox.playback.fake import FakePlayer


def test_play_pause_while_playing_pauses_once() -> None:
    player = FakePlayer()
    player.load("/proof/media.mkv")
    controller = ApplicationInputController(player)

    outcome = controller.handle(InputAction.PLAY_PAUSE)

    assert outcome is InputOutcome.PAUSED
    assert [call.operation for call in player.history] == ["load", "pause"]


def test_play_pause_while_paused_resumes_once() -> None:
    player = FakePlayer()
    player.load("/proof/media.mkv")
    player.pause()
    controller = ApplicationInputController(player)

    outcome = controller.handle(InputAction.PLAY_PAUSE)

    assert outcome is InputOutcome.RESUMED
    assert [call.operation for call in player.history] == ["load", "pause", "resume"]


def test_play_pause_while_idle_is_explicit_no_op() -> None:
    player = FakePlayer()

    outcome = ApplicationInputController(player).handle(InputAction.PLAY_PAUSE)

    assert outcome is InputOutcome.IGNORED_IDLE
    assert player.history == []


def test_application_input_controller_has_no_linux_or_evdev_dependency() -> None:
    source = inspect.getsource(application_input).lower()

    assert "evdev" not in source
    assert "linux" not in source
    assert "/dev/input" not in source
