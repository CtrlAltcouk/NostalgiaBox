"""Bounded in-process scan execution infrastructure."""

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from threading import BoundedSemaphore

from nostalgiabox.application.scans import ScanExecutorUnavailableError


class BoundedThreadScanExecutor:
    """Run at most ``max_workers`` scans with no additional unbounded queue."""

    def __init__(self, max_workers: int) -> None:
        if max_workers < 1:
            raise ValueError("scan worker count must be positive")
        self._capacity = BoundedSemaphore(max_workers)
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="nostalgiabox-scan",
        )
        self._closed = False

    def submit(self, operation: Callable[[], None]) -> None:
        if self._closed or not self._capacity.acquire(blocking=False):
            raise ScanExecutorUnavailableError("bounded scan executor has no free worker")
        try:
            future = self._executor.submit(operation)
        except BaseException:
            self._capacity.release()
            raise
        future.add_done_callback(self._release_capacity)

    def shutdown(self, *, wait: bool = True) -> None:
        self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def _release_capacity(self, _future: Future[None]) -> None:
        self._capacity.release()
