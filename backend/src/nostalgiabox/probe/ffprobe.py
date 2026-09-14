"""Fail-closed ffprobe adapter; raw JSON does not leave this infrastructure boundary."""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from nostalgiabox.domain.probe import (
    ProbeDomainError,
    ProbeFailure,
    ProbeFailureCode,
    StreamFact,
    TechnicalMetadata,
    decimal_duration_to_microseconds,
    normalized_text,
    parse_frame_rate,
)

_READ_CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True, slots=True)
class ProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class ProcessRunner(Protocol):
    def run(
        self, argv: Sequence[str], *, timeout_seconds: float, output_limit: int
    ) -> ProcessResult: ...


class ProbeRunnerError(Exception):
    def __init__(self, failure: ProbeFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


class SubprocessRunner:
    """argv-only runner which bounds output before it is accumulated in memory."""

    def run(
        self, argv: Sequence[str], *, timeout_seconds: float, output_limit: int
    ) -> ProcessResult:
        try:
            process = subprocess.Popen(
                list(argv),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
            )
        except FileNotFoundError as error:
            raise ProbeRunnerError(
                ProbeFailure(
                    ProbeFailureCode.EXECUTABLE_MISSING, "ffprobe executable is unavailable"
                )
            ) from error
        except OSError as error:
            raise ProbeRunnerError(
                ProbeFailure(ProbeFailureCode.EXECUTION_FAILED, "ffprobe could not be started")
            ) from error
        try:
            return self._collect(process, timeout_seconds, output_limit)
        except ProbeRunnerError:
            self._kill_and_reap(process)
            raise
        except OSError as error:
            self._kill_and_reap(process)
            raise ProbeRunnerError(
                ProbeFailure(ProbeFailureCode.EXECUTION_FAILED, "ffprobe output could not be read")
            ) from error

    @staticmethod
    def _collect(
        process: subprocess.Popen[bytes], timeout_seconds: float, output_limit: int
    ) -> ProcessResult:
        assert process.stdout is not None
        assert process.stderr is not None
        deadline = time.monotonic() + timeout_seconds
        stdout = bytearray()
        stderr = bytearray()
        buffers = {process.stdout.fileno(): stdout, process.stderr.fileno(): stderr}
        with selectors.DefaultSelector() as selector:
            for stream in (process.stdout, process.stderr):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ)
            while buffers:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProbeRunnerError(
                        ProbeFailure(ProbeFailureCode.TIMEOUT, "ffprobe exceeded its time limit")
                    )
                for key, _ in selector.select(remaining):
                    chunk = os.read(key.fd, _READ_CHUNK_SIZE)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        buffers.pop(key.fd)
                        continue
                    buffers[key.fd].extend(chunk)
                    if len(stdout) + len(stderr) > output_limit:
                        raise ProbeRunnerError(
                            ProbeFailure(
                                ProbeFailureCode.OUTPUT_TOO_LARGE,
                                "ffprobe output exceeded its limit",
                            )
                        )
            returncode = process.wait(timeout=max(0.0, deadline - time.monotonic()))
        return ProcessResult(returncode, bytes(stdout), bytes(stderr))

    @staticmethod
    def _kill_and_reap(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.communicate()


class FfprobeAdapter:
    """Fixed ffprobe invocation and conservative raw-payload translation."""

    def __init__(
        self,
        runner: ProcessRunner,
        *,
        executable: str = "ffprobe",
        capability_version: str = "ffprobe-v1",
        timeout_seconds: float = 15.0,
        output_limit: int = 1_000_000,
    ) -> None:
        if timeout_seconds <= 0 or output_limit < 1024 or not capability_version.strip():
            raise ValueError("invalid probe limits or capability version")
        self._runner = runner
        self._executable = executable
        self.capability_version = capability_version
        self._timeout_seconds = timeout_seconds
        self._output_limit = output_limit

    def inspect(self, path: str, observation_signature: str) -> TechnicalMetadata | ProbeFailure:
        version_failure = self._verify_version()
        if version_failure is not None:
            return version_failure
        argv = (
            self._executable,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            path,
        )
        try:
            result = self._runner.run(
                argv, timeout_seconds=self._timeout_seconds, output_limit=self._output_limit
            )
        except ProbeRunnerError as error:
            return error.failure
        if len(result.stdout) + len(result.stderr) > self._output_limit:
            return ProbeFailure(
                ProbeFailureCode.OUTPUT_TOO_LARGE, "ffprobe output exceeded its limit"
            )
        if result.returncode != 0:
            return ProbeFailure(ProbeFailureCode.NONZERO_EXIT, "ffprobe rejected the media input")
        try:
            return _parse(json.loads(result.stdout), observation_signature, self.capability_version)
        except json.JSONDecodeError:
            return ProbeFailure(
                ProbeFailureCode.MALFORMED_OUTPUT, "ffprobe returned malformed metadata"
            )
        except ProbeDomainError:
            return ProbeFailure(
                ProbeFailureCode.INVALID_METADATA, "ffprobe returned invalid media metadata"
            )
        except (KeyError, TypeError, ValueError):
            return ProbeFailure(
                ProbeFailureCode.MALFORMED_OUTPUT, "ffprobe returned malformed metadata"
            )

    def _verify_version(self) -> ProbeFailure | None:
        try:
            result = self._runner.run(
                (self._executable, "-version"),
                timeout_seconds=self._timeout_seconds,
                output_limit=self._output_limit,
            )
        except ProbeRunnerError as error:
            return error.failure
        if len(result.stdout) + len(result.stderr) > self._output_limit:
            return ProbeFailure(
                ProbeFailureCode.OUTPUT_TOO_LARGE, "ffprobe output exceeded its limit"
            )
        if result.returncode != 0:
            return ProbeFailure(ProbeFailureCode.VERSION_FAILED, "ffprobe version check failed")
        return None


def _parse(payload: object, signature: str, capability: str) -> TechnicalMetadata:
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("format"), dict)
        or not isinstance(payload.get("streams"), list)
    ):
        raise ProbeDomainError("invalid ffprobe shape")
    raw_format = payload["format"]
    duration = decimal_duration_to_microseconds(_required_text(raw_format.get("duration")))
    containers = tuple(
        item
        for item in (
            normalized_text(value)
            for value in _required_text(raw_format.get("format_name")).split(",")
        )
        if item
    )
    if not containers:
        raise ProbeDomainError("container required")
    streams = tuple(_parse_stream(raw) for raw in payload["streams"])
    return TechnicalMetadata(duration, containers, streams, signature, capability)


def _parse_stream(raw: object) -> StreamFact:
    if not isinstance(raw, dict):
        raise ProbeDomainError("stream must be object")
    kind = _bounded_text(raw.get("codec_type"), 16)
    if kind not in {"video", "audio", "subtitle"}:
        raise ProbeDomainError("stream type is unsupported")
    tags = raw.get("tags")
    dispositions = raw.get("disposition")
    if tags is not None and not isinstance(tags, dict):
        raise ProbeDomainError("stream tags must be an object")
    if dispositions is not None and not isinstance(dispositions, dict):
        raise ProbeDomainError("stream disposition must be an object")
    return StreamFact(
        kind,
        _bounded_text(raw.get("codec_name"), 96),
        _bounded_text((tags or {}).get("language"), 32),
        tuple(
            sorted(
                key
                for key, value in (dispositions or {}).items()
                if isinstance(key, str) and 0 < len(key) <= 32 and value in (1, True)
            )
        ),
        _dimension(raw.get("width")),
        _dimension(raw.get("height")),
        *(_rate(raw) or (None, None)),
    )


def _required_text(value: object) -> str:
    if not isinstance(value, str):
        raise ProbeDomainError("required metadata is not text")
    return value


def _bounded_text(value: object, limit: int) -> str | None:
    normalized = normalized_text(value, limit=limit)
    if (
        isinstance(value, str)
        and normalized is not None
        and len(" ".join(value.split()).casefold()) > limit
    ):
        raise ProbeDomainError("metadata text exceeds accepted bounds")
    return normalized


def _dimension(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= 100_000:
        raise ProbeDomainError("stream dimension is invalid")
    return value


def _rate(raw: dict[str, object]) -> tuple[int, int] | None:
    average = parse_frame_rate(raw.get("avg_frame_rate"))
    return parse_frame_rate(raw.get("r_frame_rate")) if average is None else average
