"""Deterministic fake player for application and Task 2.5 tests."""

from dataclasses import dataclass
from datetime import timedelta

from nostalgiabox.application.player import PlayerCommandError, PlayerError, PlayerState


@dataclass(frozen=True, slots=True)
class PlayerCall:
    """One recorded fake-player operation."""

    operation: str
    path: str | None = None
    position: timedelta | None = None


class FakePlayer:
    """Stateful, sleep-free Player implementation with recorded history."""

    def __init__(self) -> None:
        self.loaded_path: str | None = None
        self.history: list[PlayerCall] = []
        self._position: timedelta | None = None
        self._state = PlayerState.IDLE
        self._next_failure: PlayerError | None = None

    def fail_next(self, error: PlayerError) -> None:
        """Raise the supplied controlled failure on the next operation."""
        self._next_failure = error

    def load(self, path: str, position: timedelta = timedelta()) -> None:
        self._raise_configured_failure()
        if not path:
            raise ValueError("media path must not be empty")
        _require_non_negative_position(position)
        self.loaded_path = path
        self._position = position
        self._state = PlayerState.PLAYING
        self.history.append(PlayerCall("load", path=path, position=position))

    def seek(self, position: timedelta) -> None:
        self._raise_configured_failure()
        _require_non_negative_position(position)
        self._require_media("seek")
        self._position = position
        self.history.append(PlayerCall("seek", position=position))

    def pause(self) -> None:
        self._raise_configured_failure()
        self._require_media("pause")
        self._state = PlayerState.PAUSED
        self.history.append(PlayerCall("pause"))

    def resume(self) -> None:
        self._raise_configured_failure()
        self._require_media("resume")
        self._state = PlayerState.PLAYING
        self.history.append(PlayerCall("resume"))

    def stop(self) -> None:
        self._raise_configured_failure()
        self.loaded_path = None
        self._position = None
        self._state = PlayerState.IDLE
        self.history.append(PlayerCall("stop"))

    def get_position(self) -> timedelta | None:
        self._raise_configured_failure()
        return self._position

    def get_state(self) -> PlayerState:
        self._raise_configured_failure()
        return self._state

    def check_health(self) -> None:
        self._raise_configured_failure()

    def close(self) -> None:
        self.history.append(PlayerCall("close"))

    def _raise_configured_failure(self) -> None:
        error, self._next_failure = self._next_failure, None
        if error is not None:
            raise error

    def _require_media(self, operation: str) -> None:
        if self._state is PlayerState.IDLE:
            raise PlayerCommandError(operation, "no media loaded")


def _require_non_negative_position(position: timedelta) -> None:
    if position < timedelta():
        raise ValueError("playback position must not be negative")
