"""Integration proof against a temporary fake MPV Unix-domain socket."""

import json
import socket
import threading
from pathlib import Path
from typing import cast

import pytest

from nostalgiabox.playback.transport import MpvJsonIpcTransport


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="platform has no AF_UNIX support")
def test_transport_uses_real_unix_socket_with_fragmented_event_and_response(
    tmp_path: Path,
) -> None:
    socket_path = tmp_path / "mpv.sock"
    address_family = cast(int, vars(socket)["AF_UNIX"])
    server = socket.socket(address_family, socket.SOCK_STREAM)
    server.bind(str(socket_path))
    server.listen(1)
    server_error: list[BaseException] = []

    def serve_one_command() -> None:
        try:
            connection, _ = server.accept()
            with connection:
                request_bytes = bytearray()
                while b"\n" not in request_bytes:
                    request_bytes.extend(connection.recv(7))
                request = json.loads(bytes(request_bytes).split(b"\n", 1)[0])
                event = b'{"event":"file-loaded"}\n'
                response = (
                    json.dumps(
                        {
                            "request_id": request["request_id"],
                            "error": "success",
                            "data": "0.41.0-test",
                        }
                    ).encode()
                    + b"\n"
                )
                combined = event + response
                connection.sendall(combined[:9])
                connection.sendall(combined[9:])
        except BaseException as error:
            server_error.append(error)
        finally:
            server.close()

    thread = threading.Thread(target=serve_one_command)
    thread.start()
    transport = MpvJsonIpcTransport(str(socket_path), 2.0)
    try:
        assert transport.command(["get_property", "mpv-version"]) == "0.41.0-test"
        assert [event.name for event in transport.drain_events()] == ["file-loaded"]
    finally:
        transport.close()
        thread.join(timeout=2)

    assert not thread.is_alive()
    assert server_error == []
