"""Minimal approved-root filesystem adapter for local source availability."""

import os
from collections.abc import Iterable
from pathlib import Path

from nostalgiabox.application.sources import (
    InvalidSourceRootError,
    SourceAvailabilityResult,
)
from nostalgiabox.domain.catalogue import SourceAvailability

_DEFAULT_PROTECTED_ROOTS = (
    ()
    if os.name == "nt"
    else (
        "/etc",
        "/home",
        "/root",
        "/var/lib/nostalgiabox",
        "/var/cache/nostalgiabox",
        "/opt/nostalgiabox",
    )
)


class LocalFilesystemSourceGateway:
    """Resolve and minimally open local roots without scanning their contents."""

    def __init__(
        self,
        approved_roots: Iterable[str],
        *,
        protected_roots: Iterable[str] = _DEFAULT_PROTECTED_ROOTS,
    ) -> None:
        self._approved_roots = tuple(
            _require_deployment_root(value, "approved") for value in approved_roots
        )
        if not self._approved_roots:
            raise ValueError("at least one approved media root is required")
        self._protected_roots = tuple(
            _deployment_path(value, "protected") for value in protected_roots
        )

    def validate_root(self, configured_root: str) -> str:
        """Return a stable lexical absolute path after current canonical validation."""
        lexical_root = _lexical_absolute_path(configured_root)
        self._resolve_allowed_directory(lexical_root)
        return str(lexical_root)

    def check(self, configured_root: str) -> SourceAvailabilityResult:
        """Re-resolve containment and minimally open the directory on every check."""
        try:
            canonical_root = self._resolve_allowed_directory(
                _lexical_absolute_path(configured_root)
            )
            with os.scandir(canonical_root) as entries:
                next(entries, None)
        except PermissionError:
            return SourceAvailabilityResult(
                SourceAvailability.PERMISSION_DENIED,
                "source.permission_denied",
                "The configured local source cannot be read by NostalgiaBox.",
            )
        except InvalidSourceRootError:
            return SourceAvailabilityResult(
                SourceAvailability.INVALID_ROOT,
                "source.invalid_root",
                "The configured local source is missing, not a directory, "
                "or outside approved roots.",
            )
        except OSError:
            return SourceAvailabilityResult(
                SourceAvailability.UNAVAILABLE,
                "source.unavailable",
                "The configured local source is currently unavailable.",
            )
        return SourceAvailabilityResult(SourceAvailability.AVAILABLE)

    def _resolve_allowed_directory(self, lexical_root: Path) -> Path:
        try:
            canonical_root = lexical_root.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise InvalidSourceRootError("configured local source root is invalid") from error
        if not canonical_root.is_dir():
            raise InvalidSourceRootError("configured local source root is not a directory")
        if not any(_contains(root, canonical_root) for root in self._approved_roots):
            raise InvalidSourceRootError("configured local source root is outside approved roots")
        if any(_contains(root, canonical_root) for root in self._protected_roots):
            raise InvalidSourceRootError("configured local source root is protected")
        return canonical_root


def _lexical_absolute_path(value: str) -> Path:
    if not value or value != value.strip() or "\x00" in value:
        raise InvalidSourceRootError("configured local source root is malformed")
    try:
        candidate = Path(value)
    except (OSError, ValueError) as error:
        raise InvalidSourceRootError("configured local source root is malformed") from error
    if not candidate.is_absolute():
        raise InvalidSourceRootError("configured local source root must be absolute")
    if ".." in candidate.parts:
        raise InvalidSourceRootError("configured local source root contains traversal")
    return Path(os.path.abspath(candidate))


def _require_deployment_root(value: str, name: str) -> Path:
    root = _deployment_path(value, name)
    try:
        canonical = root.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError(f"{name} root {value!r} does not exist") from error
    if not canonical.is_dir():
        raise ValueError(f"{name} root {value!r} is not a directory")
    return canonical


def _deployment_path(value: str, name: str) -> Path:
    if not value or "\x00" in value:
        raise ValueError(f"{name} root must not be blank or contain NUL")
    root = Path(value)
    if not root.is_absolute():
        raise ValueError(f"{name} root must be absolute")
    return root.resolve(strict=False)


def _contains(parent: Path, candidate: Path) -> bool:
    return candidate == parent or candidate.is_relative_to(parent)
