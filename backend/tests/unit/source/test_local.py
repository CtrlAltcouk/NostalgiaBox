"""Approved-root containment and minimal local availability tests."""

import os
import stat
from pathlib import Path
from typing import NoReturn

import pytest

from nostalgiabox.application.sources import InvalidSourceRootError
from nostalgiabox.domain.catalogue import SourceAvailability
from nostalgiabox.source.local import LocalFilesystemSourceGateway


def test_approved_root_itself_and_descendant_are_accepted(tmp_path: Path) -> None:
    approved = tmp_path / "media"
    descendant = approved / "family"
    descendant.mkdir(parents=True)
    gateway = LocalFilesystemSourceGateway([str(approved)])

    assert gateway.validate_root(str(approved)) == str(approved.absolute())
    assert gateway.validate_root(str(descendant)) == str(descendant.absolute())
    assert gateway.check(str(descendant)).availability is SourceAvailability.AVAILABLE


def test_sibling_prefix_traversal_and_outside_absolute_paths_are_rejected(
    tmp_path: Path,
) -> None:
    approved = tmp_path / "media"
    sibling = tmp_path / "media2"
    outside = tmp_path / "outside"
    approved.mkdir()
    sibling.mkdir()
    outside.mkdir()
    gateway = LocalFilesystemSourceGateway([str(approved)])

    for candidate in (
        sibling,
        outside,
        Path(f"{approved}{os.sep}..{os.sep}outside"),
    ):
        with pytest.raises(InvalidSourceRootError):
            gateway.validate_root(str(candidate))


def test_relative_nul_missing_and_file_roots_are_controlled(tmp_path: Path) -> None:
    approved = tmp_path / "media"
    approved.mkdir()
    file_root = approved / "video.mkv"
    file_root.write_bytes(b"not media")
    missing = approved / "missing"
    gateway = LocalFilesystemSourceGateway([str(approved)])

    with pytest.raises(InvalidSourceRootError):
        gateway.validate_root("relative/path")
    with pytest.raises(InvalidSourceRootError):
        gateway.validate_root(f"{approved}\x00bad")
    assert gateway.check(str(missing)).availability is SourceAvailability.INVALID_ROOT
    assert gateway.check(str(file_root)).availability is SourceAvailability.INVALID_ROOT


def test_symlink_escape_and_nested_symlink_escape_are_rejected(tmp_path: Path) -> None:
    approved = tmp_path / "media"
    outside = tmp_path / "outside"
    nested = approved / "nested"
    approved.mkdir()
    outside.mkdir()
    nested.mkdir()
    direct_link = approved / "escape"
    nested_link = nested / "escape"
    _symlink_or_skip(direct_link, outside)
    _symlink_or_skip(nested_link, outside)
    gateway = LocalFilesystemSourceGateway([str(approved)])

    with pytest.raises(InvalidSourceRootError):
        gateway.validate_root(str(direct_link))
    with pytest.raises(InvalidSourceRootError):
        gateway.validate_root(str(nested_link))


def test_inside_symlink_is_allowed_but_retarget_escape_fails_next_check(tmp_path: Path) -> None:
    approved = tmp_path / "media"
    inside = approved / "inside"
    outside = tmp_path / "outside"
    approved.mkdir()
    inside.mkdir()
    outside.mkdir()
    link = approved / "selected"
    _symlink_or_skip(link, inside)
    gateway = LocalFilesystemSourceGateway([str(approved)])
    configured = gateway.validate_root(str(link))

    assert configured == str(link.absolute())
    assert gateway.resolve_root_for_access(configured) == inside.resolve(strict=True)
    assert gateway.check(configured).availability is SourceAvailability.AVAILABLE

    link.unlink()
    _symlink_or_skip(link, outside)
    result = gateway.check(configured)
    assert result.availability is SourceAvailability.INVALID_ROOT
    assert result.error_code == "source.invalid_root"


def test_protected_path_is_not_granted_by_user_input(tmp_path: Path) -> None:
    approved = tmp_path / "media"
    protected = tmp_path / "protected"
    approved.mkdir()
    protected.mkdir()
    gateway = LocalFilesystemSourceGateway(
        [str(approved), str(protected)], protected_roots=[str(protected)]
    )

    with pytest.raises(InvalidSourceRootError, match="protected"):
        gateway.validate_root(str(protected))


def test_explicit_expert_root_is_accepted_but_arbitrary_path_is_not(tmp_path: Path) -> None:
    normal = tmp_path / "normal"
    expert = tmp_path / "external-volume"
    arbitrary = tmp_path / "arbitrary"
    normal.mkdir()
    expert.mkdir()
    arbitrary.mkdir()
    gateway = LocalFilesystemSourceGateway([str(normal), str(expert)])

    assert gateway.validate_root(str(expert)) == str(expert.absolute())
    with pytest.raises(InvalidSourceRootError):
        gateway.validate_root(str(arbitrary))


@pytest.mark.skipif(
    os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="real chmod permission behavior requires a non-root POSIX process",
)
def test_real_unreadable_directory_reports_permission_denied(tmp_path: Path) -> None:
    approved = tmp_path / "media"
    unreadable = approved / "unreadable"
    unreadable.mkdir(parents=True)
    gateway = LocalFilesystemSourceGateway([str(approved)])
    configured = gateway.validate_root(str(unreadable))
    original_mode = stat.S_IMODE(unreadable.stat().st_mode)
    try:
        unreadable.chmod(0)
        result = gateway.check(configured)
    finally:
        unreadable.chmod(original_mode)

    assert result.availability is SourceAvailability.PERMISSION_DENIED
    assert result.error_code == "source.permission_denied"


@pytest.mark.parametrize("failure_stage", ["resolve", "stat", "scandir"])
def test_permission_denial_is_classified_at_each_filesystem_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
) -> None:
    approved = tmp_path / "media"
    selected = approved / "selected"
    selected.mkdir(parents=True)
    gateway = LocalFilesystemSourceGateway([str(approved)])

    def deny(*args: object, **kwargs: object) -> NoReturn:
        raise PermissionError

    if failure_stage == "resolve":
        monkeypatch.setattr(Path, "resolve", deny)
    elif failure_stage == "stat":
        monkeypatch.setattr(Path, "stat", deny)
    else:
        monkeypatch.setattr(os, "scandir", deny)

    result = gateway.check(str(selected))

    assert result.availability is SourceAvailability.PERMISSION_DENIED
    assert result.error_code == "source.permission_denied"
    assert result.error_message == "The configured local source cannot be read by NostalgiaBox."


def test_validate_root_sanitizes_permission_denial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    approved = tmp_path / "media"
    selected = approved / "selected"
    selected.mkdir(parents=True)
    gateway = LocalFilesystemSourceGateway([str(approved)])

    def deny(*args: object, **kwargs: object) -> NoReturn:
        raise PermissionError("raw operating-system detail")

    monkeypatch.setattr(Path, "resolve", deny)

    with pytest.raises(InvalidSourceRootError, match="cannot be inspected") as captured:
        gateway.validate_root(str(selected))

    assert "raw operating-system detail" not in str(captured.value)


def test_miscellaneous_resolution_io_failure_is_sanitized_as_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    approved = tmp_path / "media"
    selected = approved / "selected"
    selected.mkdir(parents=True)
    gateway = LocalFilesystemSourceGateway([str(approved)])

    def fail(*args: object, **kwargs: object) -> NoReturn:
        raise OSError("raw operating-system detail")

    monkeypatch.setattr(Path, "resolve", fail)

    result = gateway.check(str(selected))

    assert result.availability is SourceAvailability.UNAVAILABLE
    assert result.error_code == "source.unavailable"
    assert result.error_message is not None
    assert "raw operating-system detail" not in result.error_message


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlink unavailable: {type(error).__name__}")
