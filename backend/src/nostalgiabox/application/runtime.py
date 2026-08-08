"""Application orchestration for authoritative wall-clock channel playback."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from nostalgiabox.application.player import Player, PlayerError
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


class ChannelRuntime:
    """Coordinate persisted timeline truth with a replaceable player port."""

    def __init__(
        self,
        clock: Clock,
        timeline_source: ChannelTimelineSource,
        media_location_source: MediaLocationSource,
        player: Player,
    ) -> None:
        self._clock = clock
        self._timeline_source = timeline_source
        self._media_location_source = media_location_source
        self._player = player
        self._timeline: ChannelTimeline | None = None
        self._snapshot: RuntimeSnapshot | None = None

    def synchronise(self, channel_id: ChannelId) -> RuntimeSnapshot:
        """Perform an initial wall-clock tune without prior playback state."""
        timeline = self._timeline_source.load(channel_id)
        snapshot = self._resolve(timeline, RuntimeAction.INITIAL_TUNE)
        self._load(snapshot)
        self._timeline = timeline
        self._snapshot = snapshot
        return snapshot

    def tick(self) -> RuntimeSnapshot:
        """Advance at a boundary and avoid reloading the same active entry."""
        timeline, previous = self._require_active()
        candidate = self._resolve(timeline, RuntimeAction.NO_CHANGE)
        if candidate.timeline_entry_id == previous.timeline_entry_id:
            self._snapshot = candidate
            logger.debug("channel runtime unchanged", extra=_log_context(candidate))
            return candidate

        snapshot = _with_action(candidate, RuntimeAction.BOUNDARY_ADVANCE)
        self._load(snapshot)
        self._snapshot = snapshot
        return snapshot

    def resynchronise(self) -> RuntimeSnapshot:
        """Force playback back to current wall-clock truth after lost time/recovery."""
        _, previous = self._require_active()
        timeline = self._timeline_source.load(previous.channel_id)
        snapshot = self._resolve(timeline, RuntimeAction.FORCED_RESYNC)
        self._load(snapshot)
        self._timeline = timeline
        self._snapshot = snapshot
        return snapshot

    def get_snapshot(self) -> RuntimeSnapshot | None:
        """Return the latest immutable state for diagnostics/API observation."""
        return self._snapshot

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
        path = self._media_location_source.get_path(snapshot.media_item_id)
        if not path.strip():
            raise MediaLocationUnavailableError(
                f"media {snapshot.media_item_id.value!r} has no stored playback location"
            )
        context = _log_context(snapshot)
        try:
            self._player.load(path, snapshot.live_offset)
        except PlayerError:
            logger.exception("channel runtime player load failed", extra=context)
            raise
        logger.info("channel runtime loaded media", extra=context)

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
