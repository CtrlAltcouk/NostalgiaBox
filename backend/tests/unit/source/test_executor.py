"""Bounded in-process scan executor tests."""

from threading import Event

import pytest

from nostalgiabox.application.scans import ScanExecutorUnavailableError
from nostalgiabox.source.executor import BoundedThreadScanExecutor


def test_executor_has_no_queue_beyond_configured_worker_capacity() -> None:
    started = Event()
    release = Event()
    completed = Event()
    executor = BoundedThreadScanExecutor(max_workers=1)

    def blocked_operation() -> None:
        started.set()
        release.wait()
        completed.set()

    executor.submit(blocked_operation)
    assert started.wait(timeout=1)
    with pytest.raises(ScanExecutorUnavailableError, match="no free worker"):
        executor.submit(lambda: None)
    release.set()
    executor.shutdown()

    assert completed.is_set()
    with pytest.raises(ScanExecutorUnavailableError):
        executor.submit(lambda: None)


def test_executor_rejects_nonpositive_worker_count() -> None:
    with pytest.raises(ValueError, match="positive"):
        BoundedThreadScanExecutor(max_workers=0)
