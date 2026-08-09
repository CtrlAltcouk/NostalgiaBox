"""Explicit one-channel proof command attaching to migrated SQLite and MPV."""

import argparse
import json
import math
import time
from collections.abc import Callable, Sequence
from datetime import timedelta

from pydantic import ValidationError
from sqlalchemy.engine import make_url

from nostalgiabox.application.player import Player, PlayerError
from nostalgiabox.application.runtime import (
    ChannelRuntime,
    ChannelRuntimeError,
    MediaLocationUnavailableError,
    RuntimeAction,
    RuntimeFailure,
    RuntimeSnapshot,
)
from nostalgiabox.config.database import is_in_memory_sqlite_url
from nostalgiabox.config.settings import Settings
from nostalgiabox.domain.clock import SystemClock
from nostalgiabox.domain.models import ChannelId
from nostalgiabox.persistence.database import create_engine, create_session_factory
from nostalgiabox.persistence.errors import PersistenceError
from nostalgiabox.persistence.runtime_sources import (
    SqlAlchemyRuntimeDataSource,
    ensure_runtime_schema,
)
from nostalgiabox.playback.mpv import MpvPlayer


class ProofConfigurationError(Exception):
    """The explicit development proof target is unsafe or incomplete."""


def build_parser() -> argparse.ArgumentParser:
    """Build the proof parser with no production-path defaults."""
    parser = argparse.ArgumentParser(description="Run the one-channel wall-clock proof")
    parser.add_argument("--database-url", required=True, help="explicit migrated SQLite URL")
    parser.add_argument("--socket", required=True, help="explicit existing MPV IPC socket")
    parser.add_argument("--channel-number", required=True, type=_positive_integer)
    parser.add_argument("--once", action="store_true", help="synchronise once and exit")
    parser.add_argument(
        "--poll-seconds",
        type=_positive_float,
        default=1.0,
        help="continuous wall-clock poll interval (default: 1)",
    )
    parser.add_argument(
        "--command-timeout-seconds",
        type=_positive_float,
        default=2.0,
        help="MPV command timeout (default: 2)",
    )
    return parser


def validate_proof_database_url(database_url: str) -> None:
    """Require an explicit persistent SQLite target without modifying it."""
    if make_url(database_url).get_backend_name() != "sqlite":
        raise ProofConfigurationError("channel proof requires an explicit SQLite database URL")
    if is_in_memory_sqlite_url(database_url):
        raise ProofConfigurationError(
            "channel proof requires a persistent database URL; in-memory is not allowed"
        )


def run_proof_loop(
    runtime: ChannelRuntime,
    channel_id: ChannelId,
    *,
    once: bool,
    poll_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    report: Callable[[str], None] = print,
) -> RuntimeSnapshot:
    """Run the thin polling loop while keeping orchestration independently testable."""
    snapshot: RuntimeSnapshot
    try:
        snapshot = runtime.synchronise(channel_id)
    except (MediaLocationUnavailableError, PlayerError):
        failed_snapshot = runtime.get_snapshot()
        if failed_snapshot is None or once:
            raise
        snapshot = failed_snapshot
        failure = runtime.get_failure()
        if failure is not None:
            report(_failure_json(failure))
    else:
        report(_snapshot_json(snapshot))
    if once:
        return snapshot

    try:
        while True:
            sleep(poll_seconds)
            try:
                snapshot = runtime.tick()
            except (MediaLocationUnavailableError, PlayerError):
                failure = runtime.get_failure()
                if failure is not None:
                    report(_failure_json(failure))
                continue
            if snapshot.last_action in {
                RuntimeAction.BOUNDARY_ADVANCE,
                RuntimeAction.FORCED_RESYNC,
                RuntimeAction.PLAYER_RECOVERED,
            }:
                report(_snapshot_json(snapshot))
    except KeyboardInterrupt:
        report("Channel proof stopped.")
        return snapshot


def main(argv: Sequence[str] | None = None) -> int:
    """Compose explicit infrastructure, run proof, then close all resources."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_proof_database_url(args.database_url)
        settings = Settings(database_url=args.database_url)
        engine = create_engine(settings)
        player: Player | None = None
        try:
            ensure_runtime_schema(engine)
            source = SqlAlchemyRuntimeDataSource(create_session_factory(engine))
            channel = source.get_by_number(args.channel_number)
            player = _connect_player(args.socket, args.command_timeout_seconds)
            runtime = ChannelRuntime(SystemClock(), source, source, player)
            run_proof_loop(
                runtime,
                channel.id,
                once=args.once,
                poll_seconds=args.poll_seconds,
            )
        finally:
            if player is not None:
                player.close()
            engine.dispose()
    except (
        OSError,
        ValueError,
        ValidationError,
        PersistenceError,
        ChannelRuntimeError,
        PlayerError,
        ProofConfigurationError,
    ) as error:
        parser.error(str(error))
    return 0


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _connect_player(socket_path: str, timeout_seconds: float) -> Player:
    return MpvPlayer.connect(socket_path, timeout_seconds)


def _positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return parsed


def _snapshot_json(snapshot: RuntimeSnapshot) -> str:
    return json.dumps(
        {
            "action": snapshot.last_action.value,
            "channel_id": snapshot.channel_id.value,
            "channel_number": snapshot.channel_number,
            "channel_name": snapshot.channel_name,
            "timeline_entry_id": snapshot.timeline_entry_id.value,
            "media_item_id": snapshot.media_item_id.value,
            "now_utc": snapshot.now_utc.isoformat(),
            "entry_start_utc": snapshot.entry_start_utc.isoformat(),
            "entry_end_utc": snapshot.entry_end_utc.isoformat(),
            "live_offset_us": _timedelta_microseconds(snapshot.live_offset),
        },
        separators=(",", ":"),
    )


def _timedelta_microseconds(value: timedelta) -> int:
    return (value.days * 86_400 + value.seconds) * 1_000_000 + value.microseconds


def _failure_json(failure: RuntimeFailure) -> str:
    return json.dumps(
        {
            "action": "controlled_failure",
            "failure_category": failure.category.value,
            "player_failure_type": failure.player_failure_type,
            "channel_id": failure.channel_id.value,
            "timeline_entry_id": failure.timeline_entry_id.value,
            "media_item_id": failure.media_item_id.value,
            "now_utc": failure.occurred_at_utc.isoformat(),
            "message": failure.message,
        },
        separators=(",", ":"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
