"""Subprocess runner failure cleanup tests."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from nostalgiabox.domain.probe import ProbeFailureCode
from nostalgiabox.probe.ffprobe import ProbeRunnerError, ProcessResult, SubprocessRunner


def _wait_for_path(path: Path, timeout_seconds: float = 1.0) -> None:
    """Bound test setup time while waiting for a subprocess readiness signal."""
    deadline = time.monotonic() + timeout_seconds
    while not path.exists():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            pytest.fail(f"subprocess did not signal readiness: {path}")
        time.sleep(min(0.005, remaining))


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


def test_keyboard_interrupt_kills_and_reaps_the_process_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_pids: list[int] = []

    def interrupt_after_child_starts(
        process: subprocess.Popen[bytes], timeout_seconds: float, output_limit: int
    ) -> object:
        assert process.stdout is not None
        child_pid = int(process.stdout.readline())
        captured_pids.extend((process.pid, child_pid))
        raise KeyboardInterrupt

    monkeypatch.setattr(SubprocessRunner, "_collect", staticmethod(interrupt_after_child_starts))
    script = (
        "import subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        "print(child.pid, flush=True); time.sleep(30)"
    )

    with pytest.raises(KeyboardInterrupt):
        SubprocessRunner().run((sys.executable, "-c", script), timeout_seconds=5, output_limit=1024)

    for pid in captured_pids:
        try:
            state = Path(f"/proc/{pid}/stat").read_text().split()[2]
        except (FileNotFoundError, ProcessLookupError):
            continue
        assert state == "Z"


def test_timeout_kills_descendant_after_direct_child_exits_with_inherited_pipes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "descendant.pid"
    child_script = (
        "import os, pathlib, time; "
        f"pathlib.Path({str(pid_path)!r}).write_text(str(os.getpid())); "
        "time.sleep(30)"
    )
    script = (
        "import subprocess, sys; "
        f"subprocess.Popen([sys.executable, '-c', {child_script!r}]); "
        "sys.exit(0)"
    )

    collect = SubprocessRunner._collect

    def collect_after_descendant_is_ready(
        process: subprocess.Popen[bytes], timeout_seconds: float, output_limit: int
    ) -> ProcessResult:
        _wait_for_path(pid_path)
        return collect(process, timeout_seconds, output_limit)

    monkeypatch.setattr(
        SubprocessRunner, "_collect", staticmethod(collect_after_descendant_is_ready)
    )

    with pytest.raises(ProbeRunnerError) as raised:
        SubprocessRunner().run(
            (sys.executable, "-c", script), timeout_seconds=0.05, output_limit=1024
        )

    assert raised.value.failure.code is ProbeFailureCode.TIMEOUT
    descendant_pid = int(pid_path.read_text())
    try:
        state = Path(f"/proc/{descendant_pid}/stat").read_text().split()[2]
    except FileNotFoundError:
        return
    assert state == "Z"
