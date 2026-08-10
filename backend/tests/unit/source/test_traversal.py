"""Deterministic secure local traversal adapter tests."""

import os
from collections.abc import Iterable
from pathlib import Path
from unicodedata import normalize

import pytest

from nostalgiabox.application.scans import (
    TraversalEvent,
    TraversalFailedError,
    TraversalFileIssue,
    TraversalIgnored,
)
from nostalgiabox.domain.scanning import MediaFileObservation
from nostalgiabox.source.local import LocalFilesystemSourceGateway
from nostalgiabox.source.traversal import (
    LocalFilesystemTraversalGateway,
    MetadataReader,
)


def test_supported_nested_files_are_normalized_and_returned_in_deterministic_order(
    tmp_path: Path,
) -> None:
    root = tmp_path / "media"
    nested = root / "Series"
    nested.mkdir(parents=True)
    (root / "z.MP4").write_bytes(b"z")
    decomposed = "Café.mkv"
    (root / decomposed).write_bytes(b"cafe")
    (nested / "a.mkv").write_bytes(b"a")
    gateway = _gateway(root)

    observations = _observations(gateway.iterate(str(root)))

    assert [value.normalized_relative_locator for value in observations] == [
        "Café.mkv",
        "Series/a.mkv",
        "z.MP4",
    ]
    assert observations[0].original_relative_locator == decomposed
    assert observations[0].normalized_relative_locator == normalize("NFC", decomposed)
    assert observations[0].size_bytes == 4
    assert observations[0].modified_time_ns == (root / decomposed).stat().st_mtime_ns


def test_hidden_unsupported_built_in_and_configured_entries_are_ignored(
    tmp_path: Path,
) -> None:
    root = tmp_path / "media"
    root.mkdir()
    (root / ".hidden.mkv").write_bytes(b"hidden")
    (root / "notes.txt").write_text("no", encoding="utf-8")
    hidden_directory = root / ".private"
    hidden_directory.mkdir()
    (hidden_directory / "video.mkv").write_bytes(b"hidden")
    system_directory = root / "@eaDir"
    system_directory.mkdir()
    (system_directory / "video.mkv").write_bytes(b"system")
    skipped = root / "skip-this"
    skipped.mkdir()
    (skipped / "video.mkv").write_bytes(b"skip")
    (root / "visible.mkv").write_bytes(b"visible")
    gateway = _gateway(root, ignore_patterns=("skip-*",))

    events = tuple(gateway.iterate(str(root)))

    assert [item.normalized_relative_locator for item in _observations(events)] == ["visible.mkv"]
    assert sum(isinstance(event, TraversalIgnored) for event in events) == 5


def test_symlink_files_and_directories_are_never_followed(tmp_path: Path) -> None:
    root = tmp_path / "media"
    outside = tmp_path / "outside"
    inside = root / "inside"
    root.mkdir()
    outside.mkdir()
    inside.mkdir()
    (outside / "outside.mkv").write_bytes(b"outside")
    (inside / "inside.mkv").write_bytes(b"inside")
    file_link = root / "file-link.mkv"
    inside_link = root / "inside-link"
    outside_link = root / "outside-link"
    _symlink_or_skip(file_link, inside / "inside.mkv", directory=False)
    _symlink_or_skip(inside_link, inside, directory=True)
    _symlink_or_skip(outside_link, outside, directory=True)
    gateway = _gateway(root)

    events = tuple(gateway.iterate(str(root)))

    assert [item.normalized_relative_locator for item in _observations(events)] == [
        "inside/inside.mkv"
    ]
    assert (
        sum(isinstance(event, TraversalIgnored) and event.category == "symlink" for event in events)
        == 3
    )


def test_mount_boundary_is_enforced_through_injectable_metadata(tmp_path: Path) -> None:
    root = tmp_path / "media"
    mounted = root / "mounted"
    mounted.mkdir(parents=True)
    (mounted / "video.mkv").write_bytes(b"video")

    def metadata(path: Path) -> os.stat_result:
        result = os.lstat(path)
        if path.name != "mounted":
            return result
        values = list(result)
        values[2] = result.st_dev + 1
        return os.stat_result(values)

    gateway = _gateway(root, metadata_reader=metadata)

    events = tuple(gateway.iterate(str(root)))

    assert _observations(events) == ()
    assert events == (TraversalIgnored("mount_boundary"),)


def test_file_disappearing_during_observation_is_controlled(tmp_path: Path) -> None:
    root = tmp_path / "media"
    root.mkdir()
    transient = root / "transient.mkv"
    transient.write_bytes(b"video")

    def metadata(path: Path) -> os.stat_result:
        if path == transient:
            raise FileNotFoundError
        return os.lstat(path)

    gateway = _gateway(root, metadata_reader=metadata)

    events = tuple(gateway.iterate(str(root)))

    assert events == (
        TraversalFileIssue(
            "transient.mkv",
            "file.disappeared_during_scan",
            "The file disappeared before it could be observed.",
        ),
    )


def test_source_loss_or_directory_failure_raises_sanitized_traversal_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "media"
    child = root / "child"
    child.mkdir(parents=True)
    (child / "video.mkv").write_bytes(b"video")
    gateway = _gateway(root)
    real_scandir = os.scandir

    def fail_child(path: Path) -> object:
        if Path(path) == child:
            raise PermissionError("raw absolute path must not escape")
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", fail_child)

    with pytest.raises(TraversalFailedError, match="completely enumerated") as captured:
        tuple(gateway.iterate(str(root)))

    assert "raw absolute path" not in str(captured.value)


def _gateway(
    root: Path,
    *,
    ignore_patterns: tuple[str, ...] = (),
    metadata_reader: MetadataReader = os.lstat,
) -> LocalFilesystemTraversalGateway:
    return LocalFilesystemTraversalGateway(
        LocalFilesystemSourceGateway([str(root)]),
        (".mkv", ".mp4"),
        ignore_patterns,
        metadata_reader=metadata_reader,
    )


def _observations(events: Iterable[TraversalEvent]) -> tuple[MediaFileObservation, ...]:
    return tuple(event for event in events if isinstance(event, MediaFileObservation))


def _symlink_or_skip(link: Path, target: Path, *, directory: bool) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as error:
        pytest.skip(f"symlink unavailable: {type(error).__name__}")
