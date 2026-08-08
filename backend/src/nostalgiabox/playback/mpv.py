"""MPV-specific implementation of the application Player port."""

from __future__ import annotations

import math
from datetime import timedelta
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Protocol

from nostalgiabox.application.player import PlayerProtocolError, PlayerState
from nostalgiabox.playback.transport import JsonValue, MpvJsonIpcTransport


class CommandTransport(Protocol):
    """Private command surface used to isolate adapter tests from sockets."""

    def command(self, command: list[JsonValue]) -> JsonValue: ...

    def close(self) -> None: ...


def timedelta_to_mpv_seconds(position: timedelta) -> float:
    """Convert an exact position to MPV numeric seconds at the adapter boundary."""
    if position < timedelta():
        raise ValueError("playback position must not be negative")
    total_microseconds = (
        position.days * 86_400 + position.seconds
    ) * 1_000_000 + position.microseconds
    return total_microseconds / 1_000_000


def mpv_seconds_to_timedelta(value: object) -> timedelta:
    """Convert finite non-negative MPV seconds to microsecond-resolution timedelta."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("MPV playback position must be numeric")
    if not math.isfinite(value) or value < 0:
        raise ValueError("MPV playback position must be finite and non-negative")
    try:
        microseconds = int(
            (Decimal(str(value)) * Decimal(1_000_000)).quantize(
                Decimal(1), rounding=ROUND_HALF_EVEN
            )
        )
        return timedelta(microseconds=microseconds)
    except (InvalidOperation, OverflowError) as error:
        raise ValueError("MPV playback position is outside timedelta range") from error


class MpvPlayer:
    """Attach-only player adapter for one already-running MPV instance."""

    def __init__(self, transport: CommandTransport) -> None:
        self._transport = transport

    @classmethod
    def connect(cls, socket_path: str, command_timeout_seconds: float) -> MpvPlayer:
        """Build an adapter that lazily connects to a configured Unix socket."""
        return cls(MpvJsonIpcTransport(socket_path, command_timeout_seconds))

    def load(self, path: str, position: timedelta = timedelta()) -> None:
        """Replace current media and apply a per-file absolute start position."""
        if not path:
            raise ValueError("media path must not be empty")
        seconds = timedelta_to_mpv_seconds(position)
        options: dict[str, JsonValue] = {"start": _format_seconds(seconds)}
        self._transport.command(["loadfile", path, "replace", -1, options])

    def seek(self, position: timedelta) -> None:
        """Seek to an absolute, exact position from media start."""
        seconds = timedelta_to_mpv_seconds(position)
        self._transport.command(["seek", seconds, "absolute+exact"])

    def pause(self) -> None:
        self._set_property("pause", True)

    def resume(self) -> None:
        self._set_property("pause", False)

    def stop(self) -> None:
        self._transport.command(["stop"])

    def get_position(self) -> timedelta | None:
        if self._get_bool_property("idle-active"):
            return None
        raw_position = self._get_property("time-pos")
        try:
            return mpv_seconds_to_timedelta(raw_position)
        except ValueError as error:
            raise PlayerProtocolError("MPV returned invalid time-pos property data") from error

    def get_state(self) -> PlayerState:
        if self._get_bool_property("idle-active"):
            return PlayerState.IDLE
        if self._get_bool_property("pause"):
            return PlayerState.PAUSED
        return PlayerState.PLAYING

    def check_health(self) -> None:
        version = self._get_property("mpv-version")
        if not isinstance(version, str) or not version.strip():
            raise PlayerProtocolError("MPV returned invalid mpv-version property data")

    def close(self) -> None:
        self._transport.close()

    def _get_property(self, name: str) -> JsonValue:
        return self._transport.command(["get_property", name])

    def _get_bool_property(self, name: str) -> bool:
        value = self._get_property(name)
        if not isinstance(value, bool):
            raise PlayerProtocolError(f"MPV returned invalid {name} property data")
        return value

    def _set_property(self, name: str, value: JsonValue) -> None:
        self._transport.command(["set_property", name, value])


def _format_seconds(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"
