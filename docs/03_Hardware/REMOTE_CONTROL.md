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

Verified through `evtest`:

| Physical control | Linux event | Proposed NostalgiaBox action |
| --- | --- | --- |
| Home | `KEY_HOMEPAGE` | Home / return to Live TV |
| Play/Pause | `KEY_PLAYPAUSE` | PlayPause |
| Volume + | `KEY_VOLUMEUP` | VolumeUp |
| Volume - | `KEY_VOLUMEDOWN` | VolumeDown |
| Mute | `KEY_MUTE` | Mute |

The consumer-control interface advertises many possible Linux key capabilities. Capability advertisement alone does **not** mean the physical remote contains those buttons. The reference remote has no colour buttons and no numeric keypad.

## Mouse interface

The receiver exposes a standard mouse interface. The physical mouse-toggle button did not itself produce a consumer-control event during the reference `evtest` session. This is expected for many air-mouse remotes: the toggle may change the remote's internal mode and subsequent motion/button input appears on the mouse interface rather than as a keyboard/media key.

NostalgiaBox Basic Mode must not require mouse input. Mouse/air-mouse events should be ignored or disabled in the normal television interface so accidental motion cannot reveal a cursor or affect navigation.

## Basic Mode suitability

The reference remote is suitable for Basic Mode because the verified controls cover the required simple television experience:

- D-pad navigation
- OK/select
- Back
- Home
- Channel Up/Down via Page Up/Page Down
- Play/Pause
- Volume Up/Down
- Mute
- one spare/menu-style button for Info or menu use

A future remote may add Guide, Info, number keys or coloured buttons. Those are optional enhancements and must not be required by Basic Mode.

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

## Remaining validation

Before Phase 1 closes:

- test key-repeat behaviour for held navigation/channel buttons;
- test receiver after cold boot;
- test unplug/replug;
- confirm mappings are stable across reboot even if event numbers change;
- verify mouse events can be ignored/disabled cleanly;
- decide final function of the three-line/menu button.