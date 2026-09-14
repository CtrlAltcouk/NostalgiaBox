"""Subprocess runner failure cleanup tests."""

import sys

import pytest

from nostalgiabox.domain.probe import ProbeFailureCode
from nostalgiabox.probe.ffprobe import ProbeRunnerError, SubprocessRunner


def test_active_output_limit_kills_and_reaps_before_unbounded_capture() -> None:
    runner = SubprocessRunner()

    with pytest.raises(ProbeRunnerError) as raised:
        runner.run(
            (sys.executable, "-c", "import sys; sys.stdout.write('x' * 4096)"),
            timeout_seconds=5,
            output_limit=1024,
        )

    assert raised.value.failure.code is ProbeFailureCode.OUTPUT_TOO_LARGE


def test_timeout_kills_and_reaps_process_group() -> None:
    runner = SubprocessRunner()

    with pytest.raises(ProbeRunnerError) as raised:
        runner.run(
            (sys.executable, "-c", "import time; time.sleep(30)"),
            timeout_seconds=0.05,
            output_limit=1024,
        )

    assert raised.value.failure.code is ProbeFailureCode.TIMEOUT


def test_missing_executable_has_typed_sanitized_failure() -> None:
    with pytest.raises(ProbeRunnerError) as raised:
        SubprocessRunner().run(
            ("definitely-not-nostalgiabox-ffprobe", "-version"),
            timeout_seconds=1,
            output_limit=1024,
        )

    assert raised.value.failure.code is ProbeFailureCode.EXECUTABLE_MISSING
    assert "definitely" not in raised.value.failure.message
