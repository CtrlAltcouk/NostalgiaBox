"""Explicit manual validation command for an isolated MPV instance."""

import argparse
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from nostalgiabox.application.player import PlayerError
from nostalgiabox.playback.mpv import MpvPlayer


def _non_negative_seconds(value: str) -> timedelta:
    try:
        seconds = Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError("must be a numeric number of seconds") from error
    if not seconds.is_finite() or seconds < 0:
        raise argparse.ArgumentTypeError("must be finite and non-negative")
    try:
        return timedelta(microseconds=int(seconds * 1_000_000))
    except OverflowError as error:
        raise argparse.ArgumentTypeError("is outside the supported duration range") from error


def _positive_timeout(value: str) -> float:
    try:
        timeout = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a numeric number of seconds") from error
    if timeout <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return timeout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manually exercise Task 2.4 against an explicitly launched test MPV instance."
    )
    parser.add_argument("--socket", required=True, help="test MPV Unix-domain socket path")
    parser.add_argument("--media", required=True, help="operator-supplied test media path")
    parser.add_argument(
        "--start-seconds",
        type=_non_negative_seconds,
        default=timedelta(seconds=5),
        help="non-zero load position (default: 5)",
    )
    parser.add_argument(
        "--seek-seconds",
        type=_non_negative_seconds,
        default=timedelta(seconds=10),
        help="absolute seek position (default: 10)",
    )
    parser.add_argument(
        "--timeout", type=_positive_timeout, default=2.0, help="command timeout in seconds"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    player = MpvPlayer.connect(args.socket, args.timeout)
    try:
        player.check_health()
        print("health: responsive")
        player.load(args.media, args.start_seconds)
        input("loaded media at requested position; press Enter to query state/position...")
        print(f"state: {player.get_state().value}")
        print(f"position: {player.get_position()}")
        player.pause()
        input("paused; verify the picture is paused, then press Enter to resume...")
        player.resume()
        input("resumed; verify playback, then press Enter to seek absolutely...")
        player.seek(args.seek_seconds)
        input("absolute seek sent; verify the target, then press Enter to stop...")
        player.stop()
        print(f"stopped; state: {player.get_state().value}")
    except PlayerError as error:
        print(f"validation failed: {error}")
        return 1
    finally:
        player.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
