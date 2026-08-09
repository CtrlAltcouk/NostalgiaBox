"""Linux evdev adapter terminating raw input-event details."""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable, Iterator
from typing import Protocol, cast

from nostalgiabox.application.input import InputAction
from nostalgiabox.input.profile import RemoteProfile

logger = logging.getLogger(__name__)

_EV_KEY = 1
_KEY_PRESS = 1


class LinuxInputDependencyError(RuntimeError):
    """The optional Linux evdev dependency is not installed."""


class RawInputEvent(Protocol):
    """Minimum event shape consumed from python-evdev."""

    @property
    def type(self) -> int: ...

    @property
    def code(self) -> int: ...

    @property
    def value(self) -> int: ...


class InputDevice(Protocol):
    """Minimum device shape needed by the adapter."""

    def read_loop(self) -> Iterator[RawInputEvent]: ...

    def close(self) -> None: ...


type DeviceFactory = Callable[[str], InputDevice]


class LinuxInputSource:
    """Translate press events from one explicit Linux device through a profile."""

    def __init__(
        self,
        device_path: str,
        profile: RemoteProfile,
        *,
        device_factory: DeviceFactory | None = None,
    ) -> None:
        if not device_path.strip():
            raise ValueError("input device path must not be empty")
        self.profile = profile
        self._device = (device_factory or _open_evdev_device)(device_path)

    def actions(self) -> Iterator[InputAction]:
        """Yield one action per mapped key press; ignore release/repeat/unknown events."""
        for event in self._device.read_loop():
            action = translate_event(event, self.profile)
            if action is not None:
                logger.info(
                    "physical input mapped",
                    extra={
                        "action": "input_mapped",
                        "logical_input_action": action.value,
                        "input_profile": self.profile.name,
                    },
                )
                yield action

    def close(self) -> None:
        """Close the operator-selected input device."""
        self._device.close()


def translate_event(event: RawInputEvent, profile: RemoteProfile) -> InputAction | None:
    """Translate only EV_KEY press events through the selected profile."""
    if event.type != _EV_KEY or event.value != _KEY_PRESS:
        return None
    return profile.map_key(event.code)


def _open_evdev_device(device_path: str) -> InputDevice:
    try:
        evdev = importlib.import_module("evdev")
    except ModuleNotFoundError as error:
        raise LinuxInputDependencyError(
            "Linux input proof requires the optional 'linux-input' dependency"
        ) from error
    return cast(InputDevice, evdev.InputDevice(device_path))
