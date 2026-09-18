"""Generated disposable bytes only; verify bounded sampling and race rejection."""

import hashlib
import os
from dataclasses import replace
from pathlib import Path

import pytest
from tests.integration.test_probe_persistence import _media_file

from nostalgiabox.domain.catalogue import MediaFile
from nostalgiabox.fingerprint.local import FingerprintRaceError, LocalFingerprintAdapter


def _observed(path: Path) -> MediaFile:
    stat = path.stat()
    return replace(
        _media_file(),
        size_bytes=stat.st_size,
        modified_time_ns=stat.st_mtime_ns,
        device_id=stat.st_dev,
        inode_id=stat.st_ino,
    )


@pytest.mark.parametrize("size", [0, 1, 65536, 65537, 300000])
def test_full_matches_standard_sha256_and_never_changes_bytes(tmp_path: Path, size: int) -> None:
    path = tmp_path / "generated.mkv"
    data = b"x" * size
    path.write_bytes(data)
    before = path.stat()
    adapter = LocalFingerprintAdapter()
    full = adapter.full_sha256(path, _observed(path))
    assert full.digest == hashlib.sha256(data).hexdigest()
    assert full.version == 1
    assert adapter.quick(path, _observed(path)) == adapter.quick(path, _observed(path))
    assert path.read_bytes() == data
    assert path.stat().st_mtime_ns == before.st_mtime_ns


def test_real_unsampled_collision_is_candidate_only(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    data = bytearray(b"a" * 400000)
    left.write_bytes(data)
    data[80000] = ord("b")
    right.write_bytes(data)
    adapter = LocalFingerprintAdapter()
    assert adapter.quick(left, _observed(left)) == adapter.quick(right, _observed(right))
    assert adapter.full_sha256(left, _observed(left)) != adapter.full_sha256(
        right, _observed(right)
    )


def test_old_observation_and_final_symlink_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"a")
    expected = _observed(path)
    path.write_bytes(b"changed")
    with pytest.raises(FingerprintRaceError):
        LocalFingerprintAdapter().quick(path, expected)
    alias = tmp_path / "alias"
    alias.symlink_to(path)
    with pytest.raises(OSError):
        LocalFingerprintAdapter().quick(alias, _observed(path))


def test_fifo_is_rejected_without_blocking(tmp_path: Path) -> None:
    path = tmp_path / "fifo"
    os.mkfifo(path)
    with pytest.raises(FingerprintRaceError):
        LocalFingerprintAdapter().quick(path, _observed(path))


def test_locator_swap_during_read_rejects_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"first")
    expected = _observed(path)
    actual_stat = os.stat
    swapped = False

    def swap_stat(path_arg: str | Path, *, follow_symlinks: bool = True) -> os.stat_result:
        nonlocal swapped
        if not swapped:
            swapped = True
            replacement = tmp_path / "replacement"
            replacement.write_bytes(b"other")
            replacement.replace(path)
        return actual_stat(path_arg, follow_symlinks=follow_symlinks)

    monkeypatch.setattr("nostalgiabox.fingerprint.local.os.stat", swap_stat)
    with pytest.raises(FingerprintRaceError):
        LocalFingerprintAdapter().full_sha256(path, expected)


def test_quick_reads_at_most_three_fixed_samples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    path = tmp_path / "large"
    path.write_bytes(b"a" * 2_000_000)
    sizes: list[int] = []

    class Reader(io.BufferedReader):
        def read(self, size: int | None = -1) -> bytes:
            result = super().read(size)
            sizes.append(len(result))
            return result

    def open_reader(fd: int, mode: str) -> Reader:
        assert mode == "rb"
        return Reader(io.FileIO(fd, mode="rb", closefd=True))

    monkeypatch.setattr("nostalgiabox.fingerprint.local.os.fdopen", open_reader)
    LocalFingerprintAdapter().quick(path, _observed(path))
    assert sizes == [65536, 65536, 65536]
