"""ffprobe adapter translation and bounded runner tests."""

import json
from collections.abc import Sequence

import pytest

from nostalgiabox.domain.probe import ProbeFailure, ProbeFailureCode, TechnicalMetadata
from nostalgiabox.probe.ffprobe import (
    FfprobeAdapter,
    ProbeRunnerError,
    ProcessResult,
)


class FakeRunner:
    def __init__(self, *results: ProcessResult | Exception) -> None:
        self._results = list(results)
        self.argvs: list[tuple[str, ...]] = []

    def run(
        self, argv: tuple[str, ...], *, timeout_seconds: float, output_limit: int
    ) -> ProcessResult:
        self.argvs.append(argv)
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _version() -> ProcessResult:
    return ProcessResult(0, b"ffprobe version 7.1\n", b"")


def _success(**changes: object) -> ProcessResult:
    payload: dict[str, object] = {
        "format": {"duration": "1.0000005", "format_name": "matroska,webm"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "30000/1001",
                "r_frame_rate": "25/1",
                "tags": {"language": "ENG"},
                "disposition": {"default": 1, "forced": 0},
            },
            {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "en"}},
            {"codec_type": "subtitle", "codec_name": "subrip", "disposition": {"forced": 1}},
        ],
    }
    payload.update(changes)
    return ProcessResult(0, json.dumps(payload).encode(), b"")


def test_adapter_returns_typed_facts_and_fixed_argv() -> None:
    runner = FakeRunner(_version(), _success())

    result = FfprobeAdapter(runner).inspect("/private/movie.mkv", "sig")

    assert isinstance(result, TechnicalMetadata)
    assert result.duration_us == 1_000_001
    assert result.containers == ("matroska", "webm")
    assert result.streams[0].language == "eng"
    assert result.streams[0].frame_rate_numerator == 30_000
    assert result.streams[0].disposition == ("default",)
    assert runner.argvs == [
        ("ffprobe", "-version"),
        (
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            "/private/movie.mkv",
        ),
    ]


@pytest.mark.parametrize(
    ("probe_result", "expected"),
    [
        (ProcessResult(1, b"", b"/secret/token"), ProbeFailureCode.NONZERO_EXIT),
        (ProcessResult(0, b"{", b""), ProbeFailureCode.MALFORMED_OUTPUT),
        (ProcessResult(0, b"x" * 2048, b""), ProbeFailureCode.OUTPUT_TOO_LARGE),
    ],
)
def test_adapter_returns_sanitized_typed_probe_failures(
    probe_result: ProcessResult, expected: ProbeFailureCode
) -> None:
    result = FfprobeAdapter(FakeRunner(_version(), probe_result), output_limit=1024).inspect(
        "/private/movie.mkv", "sig"
    )

    assert isinstance(result, ProbeFailure)
    assert result.code is expected
    assert "/secret" not in result.message


def test_adapter_maps_missing_executable_without_diagnostics() -> None:
    missing = ProbeRunnerError(
        ProbeFailure(ProbeFailureCode.EXECUTABLE_MISSING, "ffprobe executable is unavailable")
    )

    result = FfprobeAdapter(FakeRunner(missing)).inspect("x", "sig")

    assert isinstance(result, ProbeFailure)
    assert result.code is ProbeFailureCode.EXECUTABLE_MISSING


def test_adapter_maps_version_failure_and_probe_timeout() -> None:
    version_failure = FfprobeAdapter(FakeRunner(ProcessResult(1, b"", b"boom"))).inspect("x", "sig")
    timeout = ProbeRunnerError(
        ProbeFailure(ProbeFailureCode.TIMEOUT, "ffprobe exceeded its time limit")
    )
    probe_failure = FfprobeAdapter(FakeRunner(_version(), timeout)).inspect("x", "sig")

    assert isinstance(version_failure, ProbeFailure)
    assert version_failure.code is ProbeFailureCode.VERSION_FAILED
    assert isinstance(probe_failure, ProbeFailure)
    assert probe_failure.code is ProbeFailureCode.TIMEOUT


def test_unknown_average_rate_falls_back_to_r_frame_rate() -> None:
    payload = json.loads(_success().stdout)
    streams = payload["streams"]
    assert isinstance(streams, list)
    streams[0]["avg_frame_rate"] = "0/0"
    streams[0]["r_frame_rate"] = "25/1"
    result = FfprobeAdapter(
        FakeRunner(_version(), ProcessResult(0, json.dumps(payload).encode(), b""))
    ).inspect("x", "sig")

    assert isinstance(result, TechnicalMetadata)
    assert (result.streams[0].frame_rate_numerator, result.streams[0].frame_rate_denominator) == (
        25,
        1,
    )


def test_invalid_average_rate_is_invalid_metadata_not_fallback() -> None:
    payload = json.loads(_success().stdout)
    streams = payload["streams"]
    assert isinstance(streams, list)
    streams[0]["avg_frame_rate"] = "bad-rate"
    result = FfprobeAdapter(
        FakeRunner(_version(), ProcessResult(0, json.dumps(payload).encode(), b""))
    ).inspect("x", "sig")

    assert isinstance(result, ProbeFailure)
    assert result.code is ProbeFailureCode.INVALID_METADATA
