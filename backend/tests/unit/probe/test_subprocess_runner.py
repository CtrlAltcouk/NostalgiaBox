"""Subprocess runner failure cleanup tests."""

import os
import sys
from pathlib import Path

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


def test_timeout_after_child_closes_output_is_still_killed_and_reaped(tmp_path: Path) -> None:
    """A child may close stdout/stderr before sleeping; wait() must not leak it."""
    pid_path = tmp_path / "child.pid"
    script = (
        "import os, pathlib, sys, time; "
        f"pathlib.Path({str(pid_path)!r}).write_text(str(os.getpid())); "
        "sys.stdout.close(); sys.stderr.close(); time.sleep(30)"
    )

    with pytest.raises(ProbeRunnerError) as raised:
        SubprocessRunner().run(
            (sys.executable, "-c", script), timeout_seconds=0.05, output_limit=1024
        )

    assert raised.value.failure.code is ProbeFailureCode.TIMEOUT
    child_pid = int(pid_path.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)


def test_missing_executable_has_typed_sanitized_failure() -> None:
    with pytest.raises(ProbeRunnerError) as raised:
        SubprocessRunner().run(
            ("definitely-not-nostalgiabox-ffprobe", "-version"),
            timeout_seconds=1,
            output_limit=1024,
        )

    assert raised.value.failure.code is ProbeFailureCode.EXECUTABLE_MISSING
    assert "definitely" not in raised.value.failure.message
