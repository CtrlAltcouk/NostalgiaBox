"""Explicit reference-hardware logical-input and playback proof command."""

import argparse
import json
import math
from collections.abc import Callable, Sequence

from nostalgiabox.application.input import ApplicationInputController, InputAction, InputOutcome
from nostalgiabox.application.player import Player, PlayerError
from nostalgiabox.input.linux import LinuxInputDependencyError, LinuxInputSource
from nostalgiabox.input.profile import NORDIC_1915_1025_CONSUMER
from nostalgiabox.playback.mpv import MpvPlayer


def build_parser() -> argparse.ArgumentParser:
    """Build a proof parser with explicit device and socket targets."""
    parser = argparse.ArgumentParser(description="Prove logical remote input against MPV")
    parser.add_argument(
        "--device",
        required=True,
        help="explicit evdev path; a stable /dev/input/by-id path is preferred",
    )
    parser.add_argument("--socket", required=True, help="explicit existing MPV IPC socket")
    parser.add_argument(
        "--command-timeout-seconds",
        type=_positive_float,
        default=2.0,
        help="MPV command/event timeout (default: 2)",
    )
    return parser


def run_input_loop(
    source: LinuxInputSource,
    controller: ApplicationInputController,
    *,
    report: Callable[[str], None] = print,
) -> None:
    """Dispatch mapped actions until Ctrl+C and visibly report each result."""
    try:
        for action in source.actions():
            outcome = controller.handle(action)
            report(_result_json(source.profile.name, action, outcome))
    except KeyboardInterrupt:
        report("Input proof stopped.")


def main(argv: Sequence[str] | None = None) -> int:
    """Attach to explicit input/MPV resources and close both on exit."""
    parser = build_parser()
    args = parser.parse_args(argv)
    player: Player | None = None
    source: LinuxInputSource | None = None
    try:
        player = _connect_player(args.socket, args.command_timeout_seconds)
        source = LinuxInputSource(args.device, NORDIC_1915_1025_CONSUMER)
        run_input_loop(source, ApplicationInputController(player))
    except (OSError, ValueError, LinuxInputDependencyError, PlayerError) as error:
        parser.error(str(error))
    finally:
        if source is not None:
            source.close()
        if player is not None:
            player.close()
    return 0


def _connect_player(socket_path: str, timeout_seconds: float) -> Player:
    return MpvPlayer.connect(socket_path, timeout_seconds)


def _positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return parsed


def _result_json(profile: str, action: InputAction, outcome: InputOutcome) -> str:
    return json.dumps(
        {
            "input_profile": profile,
            "logical_input_action": action.value,
            "outcome": outcome.value,
        },
        separators=(",", ":"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
