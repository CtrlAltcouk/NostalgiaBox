"""Physical key-to-logical-action profiles owned by input infrastructure."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from nostalgiabox.application.input import InputAction


@dataclass(frozen=True, slots=True)
class RemoteProfile:
    """Named immutable mapping from Linux key code to logical action."""

    name: str
    key_map: Mapping[int, InputAction]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("remote profile name must not be blank")
        object.__setattr__(self, "key_map", MappingProxyType(dict(self.key_map)))

    def map_key(self, key_code: int) -> InputAction | None:
        """Return the mapped action, ignoring unknown physical keys."""
        return self.key_map.get(key_code)


NORDIC_1915_1025_CONSUMER = RemoteProfile(
    name="nordic-1915-1025-consumer-control",
    key_map={164: InputAction.PLAY_PAUSE},
)
