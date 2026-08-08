# Reference USB Remote

## Device

Development reference remote: generic 2.4 GHz USB air-mouse/media remote purchased from Amazon UK (ASIN linked during development: B091KDK158).

Receiver detected by Linux as:

- USB ID: `1915:1025`
- Vendor string: Nordic Semiconductor ASA
- Product string: USB Composite Device

The receiver exposes multiple Linux input interfaces:

- Consumer Control
- Keyboard
- Mouse
- USB audio/microphone interfaces are also advertised by the composite receiver

Event numbers are not stable and must not be hard-coded. During the reference test they appeared as separate `/dev/input/event*` devices, but application support must identify devices by properties/capabilities and map their events into logical NostalgiaBox actions.

## Verified controls

### Keyboard interface

Verified through `evtest`:

| Physical control | Linux event | Proposed NostalgiaBox action |
| --- | --- | --- |
| Up | `KEY_UP` | NavigateUp |
| Down | `KEY_DOWN` | NavigateDown |
| Left | `KEY_LEFT` | NavigateLeft |
| Right | `KEY_RIGHT` | NavigateRight |
| Centre / OK | `KEY_ENTER` | Select |
| Three-line / menu button | observed as `KEY_COMPOSE` during initial test | Menu/Info (final behaviour TBD) |
| Page Up | `KEY_PAGEUP` | ChannelUp |
| Page Down | `KEY_PAGEDOWN` | ChannelDown |
| Back/Delete-style button | `KEY_BACKSPACE` | Back |

### Consumer-control interface

Verified through `evtest` and appliance suspend testing:

| Physical control | Linux event | Proposed NostalgiaBox action |
| --- | --- | --- |
| Power | `KEY_POWER` | Standby / Suspend |
| Home | `KEY_HOMEPAGE` | Home / return to Live TV |
| Play/Pause | `KEY_PLAYPAUSE` | PlayPause |
| Volume + | `KEY_VOLUMEUP` | VolumeUp |
| Volume - | `KEY_VOLUMEDOWN` | VolumeDown |
| Mute | `KEY_MUTE` | Mute |

The consumer-control interface advertises many possible Linux key capabilities. Capability advertisement alone does **not** mean the physical remote contains those buttons. The reference remote has no colour buttons and no numeric keypad.

## Mouse interface

The receiver exposes a standard mouse interface. The physical mouse-toggle button did not itself produce a consumer-control event during the reference `evtest` session. This is expected for many air-mouse remotes: the toggle may change the remote's internal mode and subsequent motion/button input appears on the mouse interface rather than as a keyboard/media key.

NostalgiaBox Basic Mode must not require mouse input. Mouse/air-mouse events should be ignored or disabled in the normal television interface so accidental motion cannot reveal a cursor or affect navigation.

## Standby and wake behaviour

The reference remote can put the appliance into suspend while Linux is running. Its physical power button is recognised as `KEY_POWER`, and the configured system power-key policy successfully enters suspend-to-RAM (`deep` / S3).

The current Nordic `1915:1025` receiver **cannot wake the Dell OptiPlex 7050 from suspend**. The limitation was isolated to the receiver rather than the Dell platform:

- Dell BIOS `USB Wake Support` is enabled.
- Dell BIOS `Deep Sleep Control` is disabled.
- Dell BIOS `Block Sleep (S3 State)` is disabled/unchecked.
- Linux reports `deep` as the selected memory sleep mode (`s2idle [deep]`).
- The Intel XHCI controller (`XHC`, PCI `0000:00:14.0`) is wake-enabled.
- USB root-hub wake was enabled during diagnostics.
- A normal USB keyboard successfully wakes the appliance from S3 using the same platform configuration.
- The Nordic receiver does not expose a usable device-level `power/wakeup` control and did not wake the appliance with any tested remote button.

Therefore the reference remote is accepted for development and for initiating standby, but it is **not suitable as the final production remote/receiver if remote power-on from standby is required**.

The preferred replacement is a USB HID remote/receiver that explicitly supports USB remote wake from S3 (or otherwise behaves as a wake-capable USB keyboard). Until that replacement is selected, the appliance can be woken using the physical chassis power button or a compatible wake-capable USB HID device.

This is a known hardware-accessory limitation and does not block Phase 2 software architecture work.

## Basic Mode suitability

The reference remote is suitable for Basic Mode development because the verified controls cover the required simple television experience:

- D-pad navigation
- OK/select
- Back
- Home
- Channel Up/Down via Page Up/Page Down
- Play/Pause
- Volume Up/Down
- Mute
- Power-to-standby while the appliance is awake
- one spare/menu-style button for Info or menu use

A future remote may add Guide, Info, number keys or coloured buttons. Those are optional enhancements and must not be required by Basic Mode.

For the final household appliance, the replacement remote/receiver should also support waking the machine from S3 so that one remote can provide the complete standby/resume experience.

## Input design requirement

NostalgiaBox must implement a logical input abstraction rather than scattering raw Linux key codes throughout application code:

```text
Physical remote
  -> Linux evdev event
  -> device/profile mapping
  -> NostalgiaBox logical action
  -> UI/playback behaviour
```

This allows future remotes to be supported by adding or editing a profile without changing navigation or playback logic.

## Phase 1 closure status

Phase 1 accepts the reference remote with the documented wake limitation above. The verified key map is sufficient to proceed with Phase 2, while final remote selection remains an accessory decision to resolve before the complete sofa-only Basic Mode experience is released.

Remaining remote polish can be completed alongside the production input adapter:

- confirm final key-repeat/debounce behaviour;
- verify mouse events are ignored/disabled cleanly by the production TV UI;
- decide the final function of the three-line/menu button;
- validate the eventual replacement wake-capable remote/receiver.