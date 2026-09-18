"""Read-only, fixed-version local hashing with descriptor and locator race checks."""

import hashlib
import os
import stat
from pathlib import Path

from nostalgiabox.domain.catalogue import MediaFile
from nostalgiabox.domain.identity import FingerprintResult, IdentityEvidenceKind


class FingerprintRaceError(RuntimeError):
    """The requested observation no longer identifies the opened regular file."""


class LocalFingerprintAdapter:
    """Version 1 samples up to 64 KiB at start, middle and end, framing each range."""

    SAMPLE_BYTES = 64 * 1024
    full_sha256_version = 1

    def quick(self, path: str | Path, expected: MediaFile) -> FingerprintResult:
        return self._read(path, expected, full=False)

    def full_sha256(self, path: str | Path, expected: MediaFile) -> FingerprintResult:
        return self._read(path, expected, full=True)

    def _read(self, path: str | Path, expected: MediaFile, *, full: bool) -> FingerprintResult:
        # Caller resolves through the approved source gateway. Reject a final symlink
        # and nonregular descriptors as well, including FIFO opens without blocking.
        if not hasattr(os, "O_NOFOLLOW"):
            raise OSError("safe descriptor hashing is unavailable on this platform")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode) or (
                before.st_size != expected.size_bytes
                or before.st_mtime_ns != expected.modified_time_ns
                or (expected.device_id is not None and before.st_dev != expected.device_id)
                or (expected.inode_id is not None and before.st_ino != expected.inode_id)
            ):
                raise FingerprintRaceError("file does not match discovery observation")
            digest = hashlib.sha256()
            if full:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
            else:
                digest.update(b"nostalgiabox.quick.v1\0")
                digest.update(before.st_size.to_bytes(16, "big"))
                for offset in self._offsets(before.st_size):
                    handle.seek(offset)
                    chunk = handle.read(self.SAMPLE_BYTES)
                    digest.update(offset.to_bytes(16, "big"))
                    digest.update(len(chunk).to_bytes(8, "big"))
                    digest.update(chunk)
            self._require_same(before, os.fstat(handle.fileno()))
            self._require_same(before, os.stat(path, follow_symlinks=False))
        return FingerprintResult(
            IdentityEvidenceKind.FULL_SHA256 if full else IdentityEvidenceKind.QUICK,
            "sha256" if full else "sha256-sampled",
            self.full_sha256_version,
            digest.hexdigest(),
            before.st_size,
        )

    def _offsets(self, size: int) -> tuple[int, ...]:
        return tuple(
            sorted(
                {0, max(0, size // 2 - self.SAMPLE_BYTES // 2), max(0, size - self.SAMPLE_BYTES)}
            )
        )

    @staticmethod
    def _require_same(before: os.stat_result, after: os.stat_result) -> None:
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ) or not stat.S_ISREG(after.st_mode):
            raise FingerprintRaceError("file changed while fingerprinting")
