"""Versioned content identity and candidate-only quick hash policy."""

from dataclasses import replace

import pytest

from nostalgiabox.domain.identity import (
    FingerprintResult,
    IdentityEvidenceKind,
    ReconciliationState,
    confirms_duplicate,
    decide_move,
)
from tests.integration.test_probe_persistence import _media_file


@pytest.mark.parametrize("digest", ["", "a" * 63, "g" * 64, "A" * 64, "a" * 65])
def test_invalid_digest_rejected(digest: str) -> None:
    with pytest.raises(ValueError):
        FingerprintResult(IdentityEvidenceKind.FULL_SHA256, "sha256", 1, digest, 3)


@pytest.mark.parametrize(
    "algorithm,version,size", [("md5", 1, 3), ("sha256", 0, 3), ("sha256", 1, -1)]
)
def test_invalid_contract_rejected(algorithm: str, version: int, size: int) -> None:
    with pytest.raises(ValueError):
        FingerprintResult(IdentityEvidenceKind.FULL_SHA256, algorithm, version, "a" * 64, size)


def test_only_same_version_full_sha256_confirms() -> None:
    full = FingerprintResult(IdentityEvidenceKind.FULL_SHA256, "sha256", 1, "a" * 64, 3)
    quick = FingerprintResult(IdentityEvidenceKind.QUICK, "sha256-sampled", 1, "a" * 64, 3)
    assert confirms_duplicate(full, full)
    assert not confirms_duplicate(quick, quick)
    assert not confirms_duplicate(quick, full)
    assert not confirms_duplicate(full, replace(full, version=2))
    assert not confirms_duplicate(full, replace(full, size_bytes=4))


def test_unique_inode_requires_size_time_source_and_nonnull_hints() -> None:
    file = replace(_media_file(), device_id=1, inode_id=2)
    assert decide_move(file, file, candidate_count=1).state is ReconciliationState.CONFIDENT_RENAME
    for changed in (
        replace(file, device_id=None),
        replace(file, inode_id=9),
        replace(file, size_bytes=999),
        replace(file, modified_time_ns=999),
    ):
        assert (
            decide_move(file, changed, candidate_count=1).state
            is ReconciliationState.NEEDS_ATTENTION
        )
    assert decide_move(file, file, candidate_count=2).state is ReconciliationState.NEEDS_ATTENTION


def test_missing_inode_hints_and_cross_source_are_not_continuity() -> None:
    from nostalgiabox.domain.catalogue import MediaSourceId

    file = replace(_media_file(), device_id=1, inode_id=2)
    for old, new in (
        (replace(file, inode_id=None), replace(file, inode_id=None)),
        (replace(file, device_id=None), replace(file, device_id=None)),
        (file, replace(file, source_id=MediaSourceId("other"))),
    ):
        assert decide_move(old, new, candidate_count=1).state is ReconciliationState.NEEDS_ATTENTION
