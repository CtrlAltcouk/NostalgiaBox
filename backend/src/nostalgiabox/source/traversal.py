"""Deterministic non-following local filesystem discovery adapter."""

import fnmatch
import os
import stat
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol
from unicodedata import normalize

from nostalgiabox.application.scans import (
    TraversalEvent,
    TraversalFailedError,
    TraversalFileIssue,
    TraversalIgnored,
)
from nostalgiabox.application.sources import InvalidSourceRootError
from nostalgiabox.domain.scanning import MediaFileObservation

MetadataReader = Callable[[Path], os.stat_result]


class LocalRootAccessGateway(Protocol):
    """Provide the exact canonical root already authorized for filesystem access."""

    def resolve_root_for_access(self, configured_root: str) -> Path: ...


_BUILT_IN_IGNORED_DIRECTORIES = frozenset(
    value.casefold()
    for value in (".git", "lost+found", "$RECYCLE.BIN", "System Volume Information", "@eaDir")
)


class LocalFilesystemTraversalGateway:
    """Walk one validated root in lexical depth-first order without following symlinks."""

    def __init__(
        self,
        root_gateway: LocalRootAccessGateway,
        discovery_extensions: Iterable[str],
        ignore_patterns: Iterable[str] = (),
        *,
        metadata_reader: MetadataReader = os.lstat,
    ) -> None:
        extensions = tuple(extension.casefold() for extension in discovery_extensions)
        if not extensions or any(
            not extension.startswith(".") or "/" in extension or "\\" in extension
            for extension in extensions
        ):
            raise ValueError("discovery extensions must be non-empty suffixes beginning with '.'")
        self._root_gateway = root_gateway
        self._extensions = frozenset(extensions)
        self._ignore_patterns = tuple(ignore_patterns)
        self._metadata_reader = metadata_reader

    def iterate(self, configured_root: str) -> Iterable[TraversalEvent]:
        """Yield safe relative observations and bounded diagnostic events."""
        try:
            canonical_root = self._root_gateway.resolve_root_for_access(configured_root)
            root_metadata = self._metadata_reader(canonical_root)
        except (InvalidSourceRootError, OSError, RuntimeError) as error:
            raise TraversalFailedError(
                "scan.traversal_failed",
                "The configured source root could not be safely opened for traversal.",
            ) from error
        return self._walk(canonical_root, (), root_metadata.st_dev, canonical_root)

    def _walk(
        self,
        directory: Path,
        original_parent_parts: tuple[str, ...],
        root_device_id: int,
        canonical_root: Path,
    ) -> Iterable[TraversalEvent]:
        try:
            with os.scandir(directory) as handle:
                entries = sorted(
                    handle, key=lambda entry: (normalize("NFC", entry.name), entry.name)
                )
        except OSError as error:
            raise TraversalFailedError(
                "scan.traversal_failed",
                "A source directory could not be completely enumerated.",
            ) from error

        for entry in entries:
            original_parts = (*original_parent_parts, entry.name)
            original_locator = "/".join(original_parts)
            normalized_locator = "/".join(normalize("NFC", part) for part in original_parts)
            if self._is_ignored(entry.name, normalized_locator):
                yield TraversalIgnored("policy")
                continue
            try:
                if entry.is_symlink():
                    yield TraversalIgnored("symlink")
                    continue
                metadata = self._metadata_reader(Path(entry.path))
            except FileNotFoundError:
                yield TraversalFileIssue(
                    normalized_locator,
                    "file.disappeared_during_scan",
                    "The file disappeared before it could be observed.",
                )
                continue
            except OSError as error:
                raise TraversalFailedError(
                    "scan.traversal_failed",
                    "A source entry could not be safely inspected.",
                ) from error
            if stat.S_ISLNK(metadata.st_mode):
                yield TraversalIgnored("symlink")
                continue
            if metadata.st_dev != root_device_id:
                yield TraversalIgnored("mount_boundary")
                continue
            if stat.S_ISDIR(metadata.st_mode):
                child = Path(entry.path)
                try:
                    resolved_child = child.resolve(strict=True)
                except OSError as error:
                    raise TraversalFailedError(
                        "scan.traversal_failed",
                        "A source directory changed during traversal.",
                    ) from error
                if resolved_child != child.absolute():
                    yield TraversalIgnored("symlink")
                    continue
                if not resolved_child.is_relative_to(canonical_root):
                    raise TraversalFailedError(
                        "scan.traversal_failed",
                        "A source directory escaped the configured root.",
                    )
                yield from self._walk(child, original_parts, root_device_id, canonical_root)
                continue
            if not stat.S_ISREG(metadata.st_mode):
                yield TraversalIgnored("non_regular")
                continue
            if Path(entry.name).suffix.casefold() not in self._extensions:
                yield TraversalIgnored("unsupported_extension")
                continue
            yield MediaFileObservation(
                normalized_relative_locator=normalized_locator,
                original_relative_locator=original_locator,
                size_bytes=metadata.st_size,
                modified_time_ns=metadata.st_mtime_ns,
                device_id=metadata.st_dev,
                inode_id=metadata.st_ino,
            )

    def _is_ignored(self, name: str, normalized_locator: str) -> bool:
        if name.startswith(".") or name.casefold() in _BUILT_IN_IGNORED_DIRECTORIES:
            return True
        return any(
            fnmatch.fnmatchcase(normalized_locator, pattern) for pattern in self._ignore_patterns
        )
