"""Application-owned logical input values and playback dispatch."""

import logging
from enum import StrEnum

from nostalgiabox.application.player import Player, PlayerState

logger = logging.getLogger(__name__)


class InputAction(StrEnum):
    """Small logical action set required by the Phase 2 proof."""

    PLAY_PAUSE = "play_pause"


class InputOutcome(StrEnum):
    """Observable result of handling one logical input action."""

    PAUSED = "paused"
    RESUMED = "resumed"
    IGNORED_IDLE = "ignored_idle"


class ApplicationInputController:
    """Dispatch logical input to the application-facing Player port."""

    def __init__(self, player: Player) -> None:
        self._player = player

    def handle(self, action: InputAction) -> InputOutcome:
        """Handle one action without knowing its physical source."""
        state = self._player.get_state()
        if action is InputAction.PLAY_PAUSE and state is PlayerState.PLAYING:
            self._player.pause()
            outcome = InputOutcome.PAUSED
        elif action is InputAction.PLAY_PAUSE and state is PlayerState.PAUSED:
            self._player.resume()
            outcome = InputOutcome.RESUMED
        else:
            outcome = InputOutcome.IGNORED_IDLE
        logger.info(
            "logical input handled",
            extra={
                "action": "input",
                "logical_input_action": action.value,
                "input_outcome": outcome,
            },
        )
        return outcome
