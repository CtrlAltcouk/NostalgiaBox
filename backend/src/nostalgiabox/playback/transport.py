"""Persistent newline-delimited MPV JSON IPC transport."""

from __future__ import annotations

import itertools
import json
import socket
import threading
import time
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from typing import Protocol, cast

from nostalgiabox.application.player import (
    PlayerCommandError,
    PlayerProtocolError,
    PlayerTimeoutError,
    PlayerUnavailableError,
)

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]


class _SocketLike(Protocol):
    def settimeout(self, value: float | None) -> None: ...

    def connect(self, address: str) -> None: ...

    def sendall(self, data: bytes) -> None: ...

    def recv(self, size: int) -> bytes: ...

    def close(self) -> None: ...


def _unix_socket() -> _SocketLike:
    address_family = getattr(socket, "AF_UNIX", None)
    if address_family is None:
        raise PlayerUnavailableError("this platform does not support Unix-domain sockets")
    return socket.socket(address_family, socket.SOCK_STREAM)


@dataclass(frozen=True, slots=True)
class MpvEvent:
    """An unsolicited MPV event retained separately from command responses."""

    name: str
    payload: Mapping[str, JsonValue]


class MpvJsonIpcTransport:
    """Synchronous MPV transport with request correlation and event queuing."""

    def __init__(
        self,
        socket_path: str,
        command_timeout_seconds: float,
        *,
        socket_factory: Callable[[], _SocketLike] = _unix_socket,
    ) -> None:
        if not socket_path:
            raise ValueError("MPV socket path must not be empty")
        if command_timeout_seconds <= 0:
            raise ValueError("MPV command timeout must be greater than zero")
        self._socket_path = socket_path
        self._timeout = command_timeout_seconds
        self._socket_factory = socket_factory
        self._socket: _SocketLike | None = None
        self._buffer = bytearray()
        self._request_ids = itertools.count(1)
        self._pending_responses: dict[int, dict[str, JsonValue]] = {}
        self._events: list[MpvEvent] = []
        self._lock = threading.Lock()

    def command(self, command: list[JsonValue]) -> JsonValue:
        """Send one command and wait for its request-correlated response."""
        if not command or not isinstance(command[0], str):
            raise ValueError("MPV command must start with an operation name")
        operation = command[0]
        with self._lock:
            request_id = next(self._request_ids)
            request: dict[str, JsonValue] = {
                "command": command,
                "request_id": request_id,
            }
            encoded = (
                json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                + b"\n"
            )
            connection = self._connection()
            try:
                connection.sendall(encoded)
            except OSError as error:
                self._discard_connection()
                raise PlayerUnavailableError(
                    f"MPV became unavailable while sending {operation!r}"
                ) from error

            deadline = time.monotonic() + self._timeout
            response = self._wait_for_response(request_id, deadline)
            error_value = response.get("error")
            if not isinstance(error_value, str):
                raise PlayerProtocolError(
                    f"MPV response for {operation!r} has no valid error field"
                )
            if error_value != "success":
                raise PlayerCommandError(operation, error_value)
            return response.get("data")

    def drain_events(self) -> tuple[MpvEvent, ...]:
        """Return and clear unsolicited events observed while handling commands."""
        with self._lock:
            events = tuple(self._events)
            self._events.clear()
            return events

    def close(self) -> None:
        """Close the persistent connection; a later command may reconnect."""
        with self._lock:
            self._discard_connection()

    def _connection(self) -> _SocketLike:
        if self._socket is not None:
            return self._socket
        try:
            candidate = self._socket_factory()
        except PlayerUnavailableError:
            raise
        except OSError as error:
            raise PlayerUnavailableError("could not create an MPV Unix socket") from error
        try:
            candidate.settimeout(self._timeout)
            candidate.connect(self._socket_path)
        except OSError as error:
            with suppress(OSError):
                candidate.close()
            raise PlayerUnavailableError(
                f"MPV is unavailable at configured socket {self._socket_path!r}"
            ) from error
        self._socket = candidate
        return candidate

    def _wait_for_response(self, request_id: int, deadline: float) -> dict[str, JsonValue]:
        pending = self._pending_responses.pop(request_id, None)
        if pending is not None:
            return pending
        while True:
            if time.monotonic() >= deadline:
                raise self._timeout_error()
            message = self._read_message(deadline)
            event_name = message.get("event")
            if event_name is not None:
                if not isinstance(event_name, str):
                    raise PlayerProtocolError("MPV event name must be a string")
                self._events.append(MpvEvent(event_name, message.copy()))
                continue

            response_id = message.get("request_id")
            if isinstance(response_id, bool) or not isinstance(response_id, int):
                raise PlayerProtocolError("MPV command response has no valid request_id")
            if response_id == request_id:
                return message
            if response_id in self._pending_responses:
                raise PlayerProtocolError(f"MPV returned duplicate response id {response_id}")
            self._pending_responses[response_id] = message

    def _read_message(self, deadline: float) -> dict[str, JsonValue]:
        while True:
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                raw = bytes(self._buffer[:newline])
                del self._buffer[: newline + 1]
                if not raw:
                    raise PlayerProtocolError("MPV returned an empty JSON message")
                try:
                    decoded = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError) as error:
                    raise PlayerProtocolError("MPV returned malformed JSON") from error
                if not isinstance(decoded, dict):
                    raise PlayerProtocolError("MPV JSON message must be an object")
                return cast(dict[str, JsonValue], decoded)

            connection = self._connection()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise self._timeout_error()
            try:
                connection.settimeout(remaining)
                chunk = connection.recv(4096)
            except TimeoutError as error:
                raise self._timeout_error() from error
            except OSError as error:
                self._discard_connection()
                raise PlayerUnavailableError(
                    "MPV connection failed while reading a response"
                ) from error
            if not chunk:
                self._discard_connection()
                raise PlayerUnavailableError("MPV closed the IPC connection before responding")
            self._buffer.extend(chunk)

    def _timeout_error(self) -> PlayerTimeoutError:
        return PlayerTimeoutError(f"MPV command exceeded the {self._timeout:g} second timeout")

    def _discard_connection(self) -> None:
        connection, self._socket = self._socket, None
        self._buffer.clear()
        self._pending_responses.clear()
        if connection is not None:
            with suppress(OSError):
                connection.close()
