"""Read-only HTTP projection of the latest application runtime snapshot."""

from datetime import datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel

from nostalgiabox.application.runtime import RuntimeFailure, RuntimeSnapshot, RuntimeStateProvider


class RuntimeSnapshotResponse(BaseModel):
    """Serializable, path-free diagnostic runtime snapshot."""

    channel_id: str
    channel_number: int
    channel_name: str
    timeline_entry_id: str
    media_item_id: str
    now_utc: datetime
    entry_start_utc: datetime
    entry_end_utc: datetime
    live_offset_us: int
    last_action: str


class RuntimeFailureResponse(BaseModel):
    """Path-free, stack-free projection of one controlled runtime failure."""

    category: str
    message: str
    player_failure_type: str | None
    channel_id: str
    timeline_entry_id: str
    media_item_id: str
    occurred_at_utc: datetime


class RuntimeStateResponse(BaseModel):
    """Explicit active/inactive runtime observation result."""

    active: bool
    snapshot: RuntimeSnapshotResponse | None
    failure: RuntimeFailureResponse | None = None


def create_runtime_router(provider: RuntimeStateProvider | None) -> APIRouter:
    """Bind an optional read-only state provider without composing infrastructure."""
    router = APIRouter(tags=["runtime"])

    @router.get("/runtime", response_model=RuntimeStateResponse)
    def runtime_state() -> RuntimeStateResponse:
        snapshot = None if provider is None else provider.get_snapshot()
        failure_getter = None if provider is None else getattr(provider, "get_failure", None)
        failure = None if failure_getter is None else failure_getter()
        if snapshot is None:
            return RuntimeStateResponse(
                active=False,
                snapshot=None,
                failure=None if failure is None else _response_failure(failure),
            )
        return RuntimeStateResponse(
            active=True,
            snapshot=_response_snapshot(snapshot),
            failure=None if failure is None else _response_failure(failure),
        )

    return router


def _response_snapshot(snapshot: RuntimeSnapshot) -> RuntimeSnapshotResponse:
    return RuntimeSnapshotResponse(
        channel_id=snapshot.channel_id.value,
        channel_number=snapshot.channel_number,
        channel_name=snapshot.channel_name,
        timeline_entry_id=snapshot.timeline_entry_id.value,
        media_item_id=snapshot.media_item_id.value,
        now_utc=snapshot.now_utc,
        entry_start_utc=snapshot.entry_start_utc,
        entry_end_utc=snapshot.entry_end_utc,
        live_offset_us=_timedelta_microseconds(snapshot.live_offset),
        last_action=snapshot.last_action.value,
    )


def _timedelta_microseconds(value: timedelta) -> int:
    return (value.days * 86_400 + value.seconds) * 1_000_000 + value.microseconds


def _response_failure(failure: RuntimeFailure) -> RuntimeFailureResponse:
    return RuntimeFailureResponse(
        category=failure.category.value,
        message=failure.message,
        player_failure_type=failure.player_failure_type,
        channel_id=failure.channel_id.value,
        timeline_entry_id=failure.timeline_entry_id.value,
        media_item_id=failure.media_item_id.value,
        occurred_at_utc=failure.occurred_at_utc,
    )
