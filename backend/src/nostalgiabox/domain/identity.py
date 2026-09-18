"""Validated, immutable physical identity evidence; quick hashes are only hints."""

import json
import re
from dataclasses import dataclass
from enum import StrEnum

from nostalgiabox.domain.catalogue import MediaFile


class IdentityEvidenceKind(StrEnum):
    QUICK = "quick"
    FULL_SHA256 = "full_sha256"


@dataclass(frozen=True, slots=True)
class FingerprintResult:
    kind: IdentityEvidenceKind
    algorithm: str
    version: int
    digest: str
    size_bytes: int

    def __post_init__(self) -> None:
        expected = "sha256" if self.kind is IdentityEvidenceKind.FULL_SHA256 else "sha256-sampled"
        if self.algorithm != expected or self.version < 1:
            raise ValueError("invalid fingerprint algorithm or version")
        if self.size_bytes < 0 or re.fullmatch(r"[0-9a-f]{64}", self.digest) is None:
            raise ValueError("invalid fingerprint digest or size")

    @property
    def content_key(self) -> tuple[str, int, str, int]:
        return self.algorithm, self.version, self.digest, self.size_bytes


@dataclass(frozen=True, slots=True)
class FingerprintEvidence:
    id: str
    media_file_id: str
    snapshot: str
    result: FingerprintResult

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.media_file_id.strip() or not self.snapshot.strip():
            raise ValueError("fingerprint evidence requires identity and observation binding")


class ReconciliationState(StrEnum):
    CONFIDENT_RENAME = "confident_rename"
    REPLACEMENT = "replacement"
    NEEDS_ATTENTION = "needs_attention"
    NEW = "new"


@dataclass(frozen=True, slots=True)
class ReconciliationDecision:
    state: ReconciliationState
    reason: str


def observation_snapshot(file: MediaFile) -> str:
    """Bind evidence to the physical observation, not scan bookkeeping."""
    return json.dumps(
        [
            file.source_id.value,
            file.normalized_relative_locator,
            file.original_relative_locator,
            file.presence.value,
            file.size_bytes,
            file.modified_time_ns,
            file.device_id,
            file.inode_id,
        ],
        separators=(",", ":"),
    )


def inode_continuity(old: MediaFile, new: MediaFile) -> bool:
    return (
        old.source_id == new.source_id
        and old.device_id is not None
        and old.inode_id is not None
        and old.device_id == new.device_id
        and old.inode_id == new.inode_id
        and old.size_bytes is not None
        and old.modified_time_ns is not None
        and old.size_bytes == new.size_bytes
        and old.modified_time_ns == new.modified_time_ns
    )


def decide_move(old: MediaFile, new: MediaFile, *, candidate_count: int) -> ReconciliationDecision:
    if candidate_count == 1 and inode_continuity(old, new):
        return ReconciliationDecision(ReconciliationState.CONFIDENT_RENAME, "unique_local_inode")
    return ReconciliationDecision(ReconciliationState.NEEDS_ATTENTION, "insufficient_continuity")


def confirms_duplicate(left: FingerprintResult, right: FingerprintResult) -> bool:
    return (
        left.kind is IdentityEvidenceKind.FULL_SHA256
        and right.kind is IdentityEvidenceKind.FULL_SHA256
        and left.content_key == right.content_key
    )


def snapshot(file: MediaFile, source_revision: int = 1) -> str:
    """Versioned binding to the authoritative discovery and monotonic revisions."""
    return json.dumps(
        [
            "identity-observation-v2",
            file.id.value,
            file.revision,
            source_revision,
            observation_snapshot(file),
        ],
        separators=(",", ":"),
    )


@dataclass(frozen=True, slots=True)
class DuplicateReview:
    """Historical evidence stays visible; only current unconfirmed pairs need review."""

    candidate_id: str
    left: FingerprintEvidence
    right: FingerprintEvidence
    current: bool
    confirmed_group_id: str | None

    @property
    def needs_attention(self) -> bool:
        return self.current and self.confirmed_group_id is None
