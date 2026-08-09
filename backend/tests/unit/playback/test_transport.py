"""Tests for framing, correlation and typed MPV transport failures."""

import json
from collections.abc import Iterable

import pytest

from nostalgiabox.application.player import (
    PlayerCommandError,
    PlayerProtocolError,
    PlayerTimeoutError,
    PlayerUnavailableError,
)
from nostalgiabox.playback.transport import MpvJsonIpcTransport


class ScriptedSocket:
    def __init__(
        self,
        reads: Iterable[bytes | BaseException] = (),
        *,
        connect_error: OSError | None = None,
        send_error: OSError | None = None,
    ) -> None:
        self.reads = list(reads)
        self.connect_error = connect_error
        self.send_error = send_error
        self.sent: list[bytes] = []
        self.connected_to: str | None = None
        self.timeout: float | None = None
        self.closed = False

    def settimeout(self, value: float | None) -> None:
        self.timeout = value

    def connect(self, address: str) -> None:
        if self.connect_error is not None:
            raise self.connect_error
        self.connected_to = address

    def sendall(self, data: bytes) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.sent.append(data)

    def recv(self, size: int) -> bytes:
        del size
        if not self.reads:
            return b""
        result = self.reads.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    def close(self) -> None:
        self.closed = True


def _transport(sock: ScriptedSocket) -> MpvJsonIpcTransport:
    return MpvJsonIpcTransport("/test/mpv.sock", 0.25, socket_factory=lambda: sock)


def _response(request_id: int, *, data: object = None, error: object = "success") -> bytes:
    return json.dumps({"request_id": request_id, "error": error, "data": data}).encode() + b"\n"


def test_request_is_newline_delimited_json_with_request_id() -> None:
    sock = ScriptedSocket([_response(1)])

    _transport(sock).command(["get_property", "pause"])

    assert sock.sent[0].endswith(b"\n")
    assert json.loads(sock.sent[0]) == {
        "command": ["get_property", "pause"],
        "request_id": 1,
    }


def test_different_requests_receive_different_ids_on_persistent_connection() -> None:
    sock = ScriptedSocket([_response(1) + _response(2)])
    transport = _transport(sock)

    transport.command(["get_property", "pause"])
    transport.command(["get_property", "idle-active"])

    assert [json.loads(request)["request_id"] for request in sock.sent] == [1, 2]
    assert sock.connected_to == "/test/mpv.sock"


def test_matching_response_data_is_returned() -> None:
    assert _transport(ScriptedSocket([_response(1, data=42)])).command(["x"]) == 42


def test_partial_json_across_reads_is_reconstructed() -> None:
    response = _response(1, data="complete")
    sock = ScriptedSocket([response[:8], response[8:19], response[19:]])

    assert _transport(sock).command(["x"]) == "complete"


def test_multiple_messages_in_one_read_are_buffered() -> None:
    sock = ScriptedSocket([_response(1, data="first") + _response(2, data="second")])
    transport = _transport(sock)

    assert transport.command(["first"]) == "first"
    assert transport.command(["second"]) == "second"


def test_event_before_response_is_queued_not_returned() -> None:
    event = b'{"event":"file-loaded","playlist_entry_id":1}\n'
    transport = _transport(ScriptedSocket([event + _response(1, data=True)]))

    assert transport.command(["get_property", "pause"]) is True
    events = transport.drain_events()
    assert len(events) == 1
    assert events[0].name == "file-loaded"
    assert events[0].payload["playlist_entry_id"] == 1
    assert transport.drain_events() == ()


def test_wait_for_event_consumes_matching_event_and_preserves_others() -> None:
    unrelated = b'{"event":"end-file","playlist_entry_id":1,"reason":"stop"}\n'
    target = b'{"event":"start-file","playlist_entry_id":2}\n'
    transport = _transport(ScriptedSocket([_response(1) + unrelated + target]))
    transport.command(["loadfile", "/proof/media.mkv"])

    event = transport.wait_for_event(lambda item: item.name == "start-file")

    assert event.payload["playlist_entry_id"] == 2
    assert [item.name for item in transport.drain_events()] == ["end-file"]


def test_wait_for_event_preserves_interleaved_command_response() -> None:
    target = b'{"event":"file-loaded"}\n'
    sock = ScriptedSocket([_response(2, data="later") + target, _response(1)])
    transport = _transport(sock)

    event = transport.wait_for_event(lambda item: item.name == "file-loaded")

    assert event.name == "file-loaded"
    assert transport.command(["first"]) is None
    assert transport.command(["second"]) == "later"


def test_event_between_out_of_order_responses_never_becomes_response() -> None:
    event = b'{"event":"property-change","name":"pause","data":true}\n'
    sock = ScriptedSocket([_response(2, data="two") + event + _response(1, data="one")])
    transport = _transport(sock)

    assert transport.command(["one"]) == "one"
    assert transport.command(["two"]) == "two"
    assert [item.name for item in transport.drain_events()] == ["property-change"]


def test_awkward_unicode_path_is_encoded_as_one_json_value() -> None:
    path = "/media/It's & [odd] — 日本語.mkv"
    sock = ScriptedSocket([_response(1)])

    _transport(sock).command(["loadfile", path, "replace"])

    assert json.loads(sock.sent[0])["command"][1] == path
    assert path.encode() in sock.sent[0]


@pytest.mark.parametrize("message", [b"not-json\n", b"[]\n", b"\n"])
def test_malformed_json_message_is_protocol_error(message: bytes) -> None:
    with pytest.raises(PlayerProtocolError):
        _transport(ScriptedSocket([message])).command(["x"])


def test_eof_is_player_unavailable() -> None:
    sock = ScriptedSocket([b'{"request_id":1'])

    with pytest.raises(PlayerUnavailableError, match="closed"):
        _transport(sock).command(["x"])
    assert sock.closed


def test_broken_pipe_while_sending_is_player_unavailable() -> None:
    sock = ScriptedSocket(send_error=BrokenPipeError("player died"))

    with pytest.raises(PlayerUnavailableError, match="while sending"):
        _transport(sock).command(["stop"])
    assert sock.closed


@pytest.mark.parametrize(
    "connection_error", [FileNotFoundError("missing"), ConnectionRefusedError("refused")]
)
def test_missing_or_refused_socket_is_player_unavailable(connection_error: OSError) -> None:
    sock = ScriptedSocket(connect_error=connection_error)

    with pytest.raises(PlayerUnavailableError, match="configured socket"):
        _transport(sock).command(["x"])
    assert sock.closed


def test_timeout_is_typed_and_keeps_connection_closeable() -> None:
    sock = ScriptedSocket([TimeoutError("late")])
    transport = _transport(sock)

    with pytest.raises(PlayerTimeoutError, match="0.25 second"):
        transport.command(["x"])
    transport.close()
    assert sock.closed


def test_mpv_command_error_is_typed_with_operation_context() -> None:
    sock = ScriptedSocket([_response(1, error="property unavailable")])

    with pytest.raises(PlayerCommandError) as raised:
        _transport(sock).command(["get_property", "time-pos"])

    assert raised.value.operation == "get_property"
    assert raised.value.player_error == "property unavailable"


@pytest.mark.parametrize(
    "message",
    [
        b'{"error":"success"}\n',
        b'{"request_id":true,"error":"success"}\n',
        b'{"request_id":1,"error":false}\n',
        b'{"event":7}\n',
    ],
)
def test_unexpected_response_structure_is_protocol_error(message: bytes) -> None:
    with pytest.raises(PlayerProtocolError):
        _transport(ScriptedSocket([message])).command(["x"])


def test_close_releases_connection_and_next_command_reconnects() -> None:
    first = ScriptedSocket([_response(1)])
    second = ScriptedSocket([_response(2)])
    sockets = iter([first, second])
    transport = MpvJsonIpcTransport("/test/mpv.sock", 1.0, socket_factory=lambda: next(sockets))

    transport.command(["one"])
    transport.close()
    transport.command(["two"])

    assert first.closed
    assert second.connected_to == "/test/mpv.sock"
