"""Pure scanner-domain state and observation invariant tests."""

from datetime import UTC, datetime

import pytest

from nostalgiabox.domain import (
    InvalidScanIssueError,
    InvalidScanObservationError,
    InvalidScanRunError,
    InvalidScanTransitionError,
    MediaFileId,
    MediaFileObservation,
    MediaSourceId,
    ScanCounters,
    ScanIssue,
    ScanIssueId,
    ScanIssueSeverity,
    ScanKind,
    ScanRun,
    ScanRunId,
    ScanStatus,
    validate_scan_transition,
)

_NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)


def test_scan_kind_status_and_active_terminal_values_are_stable() -> None:
    assert {kind.value for kind in ScanKind} == {"full", "incremental"}
    assert {status.value for status in ScanStatus} == {
        "queued",
        "running",
        "completed",
        "cancelled",
        "interrupted",
        "failed",
    }
    assert ScanStatus.QUEUED.is_active
    assert ScanStatus.RUNNING.is_active
    assert ScanStatus.COMPLETED.is_terminal


def test_scan_state_machine_accepts_forward_transitions_and_rejects_reopening() -> None:
    for terminal in (
        ScanStatus.COMPLETED,
        ScanStatus.CANCELLED,
        ScanStatus.INTERRUPTED,
        ScanStatus.FAILED,
    ):
        validate_scan_transition(ScanStatus.RUNNING, terminal)
    validate_scan_transition(ScanStatus.QUEUED, ScanStatus.RUNNING)
    validate_scan_transition(ScanStatus.RUNNING, ScanStatus.RUNNING)

    with pytest.raises(InvalidScanTransitionError, match="cannot transition"):
        validate_scan_transition(ScanStatus.COMPLETED, ScanStatus.RUNNING)
    with pytest.raises(InvalidScanTransitionError, match="cannot transition"):
        validate_scan_transition(ScanStatus.QUEUED, ScanStatus.COMPLETED)


def test_scan_run_requires_positive_generation_nonnegative_consistent_counts_and_utc() -> None:
    with pytest.raises(InvalidScanRunError, match="generation"):
        _run(generation=0)
    with pytest.raises(InvalidScanRunError, match="negative"):
        ScanCounters(discovered=-1)
    with pytest.raises(InvalidScanRunError, match="exceed"):
        ScanCounters(discovered=1, added=2)
    with pytest.raises(InvalidScanRunError, match="aware UTC"):
        _run(queued_utc=datetime(2026, 8, 10, 12))


def test_scan_run_status_timestamp_and_error_pairs_are_enforced() -> None:
    with pytest.raises(InvalidScanRunError, match="queued"):
        _run(started_utc=_NOW)
    with pytest.raises(InvalidScanRunError, match="running"):
        _run(status=ScanStatus.RUNNING)
    with pytest.raises(InvalidScanRunError, match="terminal"):
        _run(status=ScanStatus.FAILED)
    with pytest.raises(InvalidScanRunError, match="paired"):
        _run(terminal_error_code="scan.failed")


def test_observation_cheap_signature_excludes_device_and_inode_hints() -> None:
    first = MediaFileObservation("Café.MKV", "Café.MKV", 10, 123, 1, 2)
    second = MediaFileObservation("Café.MKV", "Café.MKV", 10, 123, 9, 10)

    assert first.cheap_signature == second.cheap_signature == ("Café.MKV", 10, 123)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"normalized_relative_locator": "../escape.mkv"},
        {"normalized_relative_locator": "Café.mkv"},
        {"normalized_relative_locator": "folder\\video.mkv"},
        {"size_bytes": -1},
        {"device_id": -1},
        {"inode_id": -1},
    ],
)
def test_observation_rejects_unsafe_locator_or_negative_metadata(
    kwargs: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "normalized_relative_locator": "video.mkv",
        "original_relative_locator": "video.mkv",
        "size_bytes": 0,
        "modified_time_ns": 0,
    }
    values.update(kwargs)
    with pytest.raises(InvalidScanObservationError):
        MediaFileObservation(**values)  # type: ignore[arg-type]


def test_scan_issue_requires_safe_complete_values_and_utc() -> None:
    issue = ScanIssue(
        ScanIssueId("issue-1"),
        ScanRunId("run-1"),
        "file.changed:video.mkv",
        "file.changed_observation",
        "The cheap observation changed.",
        _NOW,
        ScanIssueSeverity.WARNING,
        MediaFileId("file-1"),
        "video.mkv",
    )
    assert issue.relative_locator == "video.mkv"

    with pytest.raises(InvalidScanIssueError, match="message"):
        ScanIssue(
            ScanIssueId("issue-2"),
            ScanRunId("run-1"),
            "key",
            "code",
            " ",
            _NOW,
            ScanIssueSeverity.ERROR,
        )


def _run(**changes: object) -> ScanRun:
    values: dict[str, object] = {
        "id": ScanRunId("run-1"),
        "source_id": MediaSourceId("source-1"),
        "kind": ScanKind.FULL,
        "generation": 1,
        "status": ScanStatus.QUEUED,
        "cancellation_requested": False,
        "queued_utc": _NOW,
    }
    values.update(changes)
    return ScanRun(**values)  # type: ignore[arg-type]
