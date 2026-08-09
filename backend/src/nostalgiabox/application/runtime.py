"""Application orchestration for authoritative wall-clock channel playback."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from nostalgiabox.application.player import (
    Player,
    PlayerCommandError,
    PlayerError,
    PlayerMediaLoadError,
    PlayerProtocolError,
    PlayerTimeoutError,
    PlayerUnavailableError,
)
from nostalgiabox.domain.clock import Clock
from nostalgiabox.domain.exceptions import TimelineNotCoveredError
from nostalgiabox.domain.models import (
    Channel,
    ChannelId,
    MediaItemId,
    TimelineEntryId,
)
from nostalgiabox.domain.time import normalize_utc
from nostalgiabox.domain.timeline import ChannelTimeline, resolve_active_entry

logger = logging.getLogger(__name__)


class ChannelRuntimeError(Exception):
    """Base class for controlled one-channel runtime failures."""


class RuntimeNotActiveError(ChannelRuntimeError):
    """A tick or resynchronisation was requested before initial tune."""


class ChannelUnavailableError(ChannelRuntimeError):
    """The requested channel or validated timeline is unavailable."""


class MediaLocationUnavailableError(ChannelRuntimeError):
    """No stored playback location exists for the active media item."""


class RuntimeTimelineNotCoveredError(ChannelRuntimeError):
    """The channel timeline does not cover the current wall-clock instant."""


class RuntimeAction(StrEnum):
    """Reason for the most recent runtime state transition."""

    INITIAL_TUNE = "initial_tune"
    NO_CHANGE = "no_change"
    BOUNDARY_ADVANCE = "boundary_advance"
    FORCED_RESYNC = "forced_resync"
    MEDIA_RETRY_SUPPRESSED = "media_retry_suppressed"
    PLAYER_RECOVERY_WAIT = "player_recovery_wait"
    PLAYER_RECOVERED = "player_recovered"


class RuntimeFailureCategory(StrEnum):
    """Stable failure categories exposed without infrastructure payloads."""

    MEDIA_LOCATION = "media_location"
    MEDIA_LOAD = "media_load"
    PLAYER_UNAVAILABLE = "player_unavailable"
    PLAYER_TIMEOUT = "player_timeout"
    PLAYER_PROTOCOL = "player_protocol"
    PLAYER_COMMAND = "player_command"


@dataclass(frozen=True, slots=True)
class RuntimeFailure:
    """Controlled failure state retaining its original typed cause internally."""

    category: RuntimeFailureCategory
    message: str
    player_failure_type: str | None
    channel_id: ChannelId
    timeline_entry_id: TimelineEntryId
    media_item_id: MediaItemId
    occurred_at_utc: datetime
    original_cause: Exception


@dataclass(frozen=True, slots=True)
class PlayerRecoveryPolicy:
    """Bound normal health checks and recovery attempts by wall-clock cadence."""

    health_check_interval: timedelta = timedelta(seconds=5)
    recovery_interval: timedelta = timedelta(seconds=5)

    def __post_init__(self) -> None:
        if self.health_check_interval <= timedelta():
            raise ValueError("player health-check interval must be positive")
        if self.recovery_interval <= timedelta():
            raise ValueError("player recovery interval must be positive")


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    """Immutable, infrastructure-free diagnostic view of runtime truth."""

    channel_id: ChannelId
    channel_number: int
    channel_name: str
    timeline_entry_id: TimelineEntryId
    media_item_id: MediaItemId
    now_utc: datetime
    entry_start_utc: datetime
    entry_end_utc: datetime
    live_offset: timedelta
    last_action: RuntimeAction


class ChannelTimelineSource(Protocol):
    """Application port for loading one validated channel timeline."""

    def load(self, channel_id: ChannelId) -> ChannelTimeline: ...


class MediaLocationSource(Protocol):
    """Application port for resolving a media identity to a player path."""

    def get_path(self, media_item_id: MediaItemId) -> str: ...


class ChannelLookup(Protocol):
    """Application port for resolving an operator-facing channel number."""

    def get_by_number(self, channel_number: int) -> Channel: ...


class RuntimeStateProvider(Protocol):
    """Read-only provider consumed by observation boundaries."""

    def get_snapshot(self) -> RuntimeSnapshot | None: ...

    def get_failure(self) -> RuntimeFailure | None: ...


class ChannelRuntime:
    """Coordinate persisted timeline truth with a replaceable player port."""

    def __init__(
        self,
        clock: Clock,
        timeline_source: ChannelTimelineSource,
        media_location_source: MediaLocationSource,
        player: Player,
        recovery_policy: PlayerRecoveryPolicy | None = None,
    ) -> None:
        self._clock = clock
        self._timeline_source = timeline_source
        self._media_location_source = media_location_source
        self._player = player
        self._recovery_policy = recovery_policy or PlayerRecoveryPolicy()
        self._timeline: ChannelTimeline | None = None
        self._snapshot: RuntimeSnapshot | None = None
        self._failure: RuntimeFailure | None = None
        self._next_health_check_utc: datetime | None = None
        self._next_recovery_utc: datetime | None = None

    def synchronise(self, channel_id: ChannelId) -> RuntimeSnapshot:
        """Perform an initial wall-clock tune without prior playback state."""
        timeline = self._timeline_source.load(channel_id)
        snapshot = self._resolve(timeline, RuntimeAction.INITIAL_TUNE)
        self._timeline = timeline
        self._snapshot = snapshot
        self._load(snapshot)
        self._mark_healthy(snapshot.now_utc)
        return snapshot

    def tick(self) -> RuntimeSnapshot:
        """Advance at a boundary and avoid reloading the same active entry."""
        timeline, previous = self._require_active()
        candidate = self._resolve(timeline, RuntimeAction.NO_CHANGE)
        if self._failure is not None:
            if self._failure.category in {
                RuntimeFailureCategory.MEDIA_LOCATION,
                RuntimeFailureCategory.MEDIA_LOAD,
            }:
                if candidate.timeline_entry_id == previous.timeline_entry_id:
                    snapshot = _with_action(candidate, RuntimeAction.MEDIA_RETRY_SUPPRESSED)
                    self._snapshot = snapshot
                    logger.debug(
                        "known media failure retry suppressed", extra=_log_context(snapshot)
                    )
                    return snapshot
            else:
                return self._recover_player(candidate)

        self._check_player_health_if_due(candidate)
        if candidate.timeline_entry_id == previous.timeline_entry_id:
            self._snapshot = candidate
            logger.debug("channel runtime unchanged", extra=_log_context(candidate))
            return candidate

        snapshot = _with_action(candidate, RuntimeAction.BOUNDARY_ADVANCE)
        self._snapshot = snapshot
        self._load(snapshot)
        self._mark_healthy(snapshot.now_utc)
        return snapshot

    def resynchronise(self) -> RuntimeSnapshot:
        """Force playback back to current wall-clock truth after lost time/recovery."""
        _, previous = self._require_active()
        timeline = self._timeline_source.load(previous.channel_id)
        snapshot = self._resolve(timeline, RuntimeAction.FORCED_RESYNC)
        self._timeline = timeline
        self._snapshot = snapshot
        self._load(snapshot)
        self._mark_healthy(snapshot.now_utc)
        return snapshot

    def get_snapshot(self) -> RuntimeSnapshot | None:
        """Return the latest immutable state for diagnostics/API observation."""
        return self._snapshot

    def get_failure(self) -> RuntimeFailure | None:
        """Return the latest controlled failure, including its typed cause internally."""
        return self._failure

    def _resolve(self, timeline: ChannelTimeline, action: RuntimeAction) -> RuntimeSnapshot:
        now_utc = normalize_utc(self._clock.now(), field_name="channel runtime clock")
        try:
            resolved = resolve_active_entry(timeline, now_utc)
        except TimelineNotCoveredError as error:
            raise RuntimeTimelineNotCoveredError(str(error)) from error
        entry = resolved.entry
        return RuntimeSnapshot(
            channel_id=timeline.channel.id,
            channel_number=timeline.channel.number,
            channel_name=timeline.channel.name,
            timeline_entry_id=entry.id,
            media_item_id=entry.media_item_id,
            now_utc=now_utc,
            entry_start_utc=entry.start_utc,
            entry_end_utc=entry.end_utc,
            live_offset=resolved.live_offset,
            last_action=action,
        )

    def _load(self, snapshot: RuntimeSnapshot) -> None:
        context = _log_context(snapshot)
        try:
            path = self._media_location_source.get_path(snapshot.media_item_id)
            if not path.strip():
                raise MediaLocationUnavailableError(
                    f"media {snapshot.media_item_id.value!r} has no stored playback location"
                )
            self._player.load(path, snapshot.live_offset)
        except (MediaLocationUnavailableError, PlayerError) as error:
            self._record_failure(snapshot, error)
            raise
        self._failure = None
        self._next_recovery_utc = None
        logger.info("channel runtime loaded media", extra=context)

    def _check_player_health_if_due(self, snapshot: RuntimeSnapshot) -> None:
        if (
            self._next_health_check_utc is not None
            and snapshot.now_utc < self._next_health_check_utc
        ):
            return
        try:
            self._player.check_health()
        except PlayerError as error:
            self._snapshot = snapshot
            self._record_failure(snapshot, error)
            raise
        self._next_health_check_utc = snapshot.now_utc + self._recovery_policy.health_check_interval

    def _recover_player(self, candidate: RuntimeSnapshot) -> RuntimeSnapshot:
        if self._next_recovery_utc is not None and candidate.now_utc < self._next_recovery_utc:
            snapshot = _with_action(candidate, RuntimeAction.PLAYER_RECOVERY_WAIT)
            self._snapshot = snapshot
            return snapshot
        try:
            self._player.check_health()
        except PlayerError as error:
            self._snapshot = candidate
            self._record_failure(candidate, error)
            raise

        timeline = self._timeline_source.load(candidate.channel_id)
        snapshot = self._resolve(timeline, RuntimeAction.PLAYER_RECOVERED)
        self._timeline = timeline
        self._snapshot = snapshot
        self._load(snapshot)
        self._mark_healthy(snapshot.now_utc)
        logger.info(
            "player health restored and runtime resynchronised", extra=_log_context(snapshot)
        )
        return snapshot

    def _record_failure(
        self, snapshot: RuntimeSnapshot, error: MediaLocationUnavailableError | PlayerError
    ) -> None:
        category = _failure_category(error)
        player_failure_type = type(error).__name__ if isinstance(error, PlayerError) else None
        self._failure = RuntimeFailure(
            category=category,
            message=str(error),
            player_failure_type=player_failure_type,
            channel_id=snapshot.channel_id,
            timeline_entry_id=snapshot.timeline_entry_id,
            media_item_id=snapshot.media_item_id,
            occurred_at_utc=snapshot.now_utc,
            original_cause=error,
        )
        if category not in {
            RuntimeFailureCategory.MEDIA_LOCATION,
            RuntimeFailureCategory.MEDIA_LOAD,
        }:
            self._next_recovery_utc = snapshot.now_utc + self._recovery_policy.recovery_interval
        context = _log_context(snapshot)
        context.update(
            failure_category=category.value,
            player_failure_type=player_failure_type,
        )
        logger.error("channel runtime controlled failure", extra=context)

    def _mark_healthy(self, now_utc: datetime) -> None:
        self._failure = None
        self._next_recovery_utc = None
        self._next_health_check_utc = now_utc + self._recovery_policy.health_check_interval

    def _require_active(self) -> tuple[ChannelTimeline, RuntimeSnapshot]:
        if self._timeline is None or self._snapshot is None:
            raise RuntimeNotActiveError("channel runtime has not been synchronised")
        return self._timeline, self._snapshot


def _with_action(snapshot: RuntimeSnapshot, action: RuntimeAction) -> RuntimeSnapshot:
    return RuntimeSnapshot(
        channel_id=snapshot.channel_id,
        channel_number=snapshot.channel_number,
        channel_name=snapshot.channel_name,
        timeline_entry_id=snapshot.timeline_entry_id,
        media_item_id=snapshot.media_item_id,
        now_utc=snapshot.now_utc,
        entry_start_utc=snapshot.entry_start_utc,
        entry_end_utc=snapshot.entry_end_utc,
        live_offset=snapshot.live_offset,
        last_action=action,
    )


def _log_context(snapshot: RuntimeSnapshot) -> dict[str, object]:
    return {
        "action": snapshot.last_action.value,
        "channel_id": snapshot.channel_id.value,
        "timeline_entry_id": snapshot.timeline_entry_id.value,
        "media_item_id": snapshot.media_item_id.value,
        "now_utc": snapshot.now_utc.isoformat(),
        "entry_start_utc": snapshot.entry_start_utc.isoformat(),
        "entry_end_utc": snapshot.entry_end_utc.isoformat(),
        "target_live_offset": str(snapshot.live_offset),
        "target_live_offset_us": _timedelta_microseconds(snapshot.live_offset),
    }


def _timedelta_microseconds(value: timedelta) -> int:
    return (value.days * 86_400 + value.seconds) * 1_000_000 + value.microseconds


def _failure_category(
    error: MediaLocationUnavailableError | PlayerError,
) -> RuntimeFailureCategory:
    if isinstance(error, MediaLocationUnavailableError):
        return RuntimeFailureCategory.MEDIA_LOCATION
    if isinstance(error, PlayerMediaLoadError):
        return RuntimeFailureCategory.MEDIA_LOAD
    if isinstance(error, PlayerUnavailableError):
        return RuntimeFailureCategory.PLAYER_UNAVAILABLE
    if isinstance(error, PlayerTimeoutError):
        return RuntimeFailureCategory.PLAYER_TIMEOUT
    if isinstance(error, PlayerProtocolError):
        return RuntimeFailureCategory.PLAYER_PROTOCOL
    if isinstance(error, PlayerCommandError):
        return RuntimeFailureCategory.PLAYER_COMMAND
    raise TypeError(f"unsupported player failure type: {type(error).__name__}")
