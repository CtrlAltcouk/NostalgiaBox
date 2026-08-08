"""Application-facing playback port and values."""

from datetime import timedelta
from enum import StrEnum
from typing import Protocol, runtime_checkable


class PlayerState(StrEnum):
    """Small playback state visible to application orchestration."""

    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"


class PlayerError(Exception):
    """Base class for controlled playback failures."""


class PlayerUnavailableError(PlayerError):
    """The player cannot be reached or disappeared during communication."""


class PlayerTimeoutError(PlayerError):
    """The player did not answer within the configured command timeout."""


class PlayerProtocolError(PlayerError):
    """The player returned data that violates the expected protocol."""


class PlayerCommandError(PlayerError):
    """The player explicitly rejected an otherwise valid command."""

    def __init__(self, operation: str, player_error: str) -> None:
        self.operation = operation
        self.player_error = player_error
        super().__init__(f"player rejected {operation!r}: {player_error}")


@runtime_checkable
class Player(Protocol):
    """Infrastructure-agnostic player operations used by application orchestration."""

    def load(self, path: str, position: timedelta = timedelta()) -> None:
        """Replace current media and begin at an absolute position."""

    def seek(self, position: timedelta) -> None:
        """Seek to an absolute position from media start."""

    def pause(self) -> None:
        """Pause current playback."""

    def resume(self) -> None:
        """Resume current playback."""

    def stop(self) -> None:
        """Unload current media and enter the idle state."""

    def get_position(self) -> timedelta | None:
        """Return current media position, or None when idle."""

    def get_state(self) -> PlayerState:
        """Return idle, playing or paused state."""

    def check_health(self) -> None:
        """Prove the player is responsive, raising a typed error otherwise."""

    def close(self) -> None:
        """Release resources owned by this adapter."""
