"""Tests for the deterministic application player fake."""

from datetime import timedelta

import pytest

from nostalgiabox.application.player import (
    Player,
    PlayerCommandError,
    PlayerState,
    PlayerUnavailableError,
)
from nostalgiabox.playback.fake import FakePlayer, PlayerCall


def test_fake_implements_player_protocol_and_starts_idle() -> None:
    player = FakePlayer()

    assert isinstance(player, Player)
    assert player.get_state() is PlayerState.IDLE
    assert player.get_position() is None


def test_fake_loads_at_exact_non_zero_position_and_records_call() -> None:
    player = FakePlayer()
    position = timedelta(minutes=3, seconds=2, microseconds=345_678)

    player.load("/media/programme.mkv", position)

    assert player.loaded_path == "/media/programme.mkv"
    assert player.get_position() == position
    assert player.get_state() is PlayerState.PLAYING
    assert player.history == [PlayerCall("load", "/media/programme.mkv", position)]


def test_fake_seek_is_absolute() -> None:
    player = FakePlayer()
    player.load("programme.mkv", timedelta(seconds=20))

    player.seek(timedelta(seconds=4))

    assert player.get_position() == timedelta(seconds=4)
    assert player.history[-1] == PlayerCall("seek", position=timedelta(seconds=4))


def test_fake_pause_resume_and_stop_transitions() -> None:
    player = FakePlayer()
    player.load("programme.mkv")

    player.pause()
    assert player.get_state() is PlayerState.PAUSED
    player.resume()
    assert player.get_state() is PlayerState.PLAYING
    player.stop()

    assert player.get_state() is PlayerState.IDLE
    assert player.get_position() is None
    assert player.loaded_path is None
    assert [call.operation for call in player.history] == ["load", "pause", "resume", "stop"]


@pytest.mark.parametrize("operation", ["load", "seek"])
def test_fake_rejects_negative_positions(operation: str) -> None:
    player = FakePlayer()
    if operation == "seek":
        player.load("programme.mkv")

    with pytest.raises(ValueError, match="must not be negative"):
        if operation == "load":
            player.load("programme.mkv", timedelta(microseconds=-1))
        else:
            player.seek(timedelta(microseconds=-1))


def test_fake_can_raise_one_configured_failure() -> None:
    player = FakePlayer()
    error = PlayerUnavailableError("simulated loss")
    player.fail_next(error)

    with pytest.raises(PlayerUnavailableError, match="simulated loss"):
        player.check_health()

    player.check_health()


def test_fake_rejects_media_operations_while_idle() -> None:
    player = FakePlayer()

    with pytest.raises(PlayerCommandError, match="no media loaded"):
        player.pause()
