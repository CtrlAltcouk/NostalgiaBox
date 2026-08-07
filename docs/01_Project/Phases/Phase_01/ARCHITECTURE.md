# Phase 1 — Hardware Validation and Appliance Base: Architecture

## Appliance model

NostalgiaBox uses a dedicated appliance model rather than a conventional desktop or browser-kiosk operating model.

Normal startup path:

```text
Power on
  -> Dell firmware / UEFI
  -> Debian 13
  -> systemd
  -> NostalgiaBox runtime/session
  -> full-screen NostalgiaBox presentation
  -> configured startup channel
```

The operating system is infrastructure, not part of the user experience.

## Runtime identity and filesystem boundaries

- `root`: administration only.
- `nostalgia`: dedicated application/service account.
- `/opt/nostalgiabox`: application source/runtime files and repository checkout.
- `/etc/nostalgiabox`: machine configuration owned/administered separately from application code.
- `/var/lib/nostalgiabox`: persistent state, database and generated metadata.
- `/var/cache/nostalgiabox`: disposable/rebuildable cache.
- `/srv/nostalgiabox/media`: optional locally stored user media.
- journald/systemd logging is preferred over ad-hoc application log files.

This separation allows application updates without overwriting user media, persistent state or machine configuration.

## Network architecture

- NetworkManager manages network interfaces and saved Wi-Fi connections.
- `systemd-resolved` provides local DNS resolution.
- `/etc/resolv.conf` is linked to `/run/systemd/resolve/stub-resolv.conf`.
- SSH is permitted for administrator/developer maintenance but is not surfaced in the television UI.
- Web administration will later bind according to the security design defined in the web UI phase.

## Input architecture

Physical input devices must be translated into logical NostalgiaBox actions.

```text
USB/HID remote
  -> Linux evdev events
  -> NostalgiaBox input adapter/profile
  -> logical actions
  -> TV UI / playback coordinator
```

Example logical actions:

- NavigateUp / NavigateDown / NavigateLeft / NavigateRight
- Select
- Back
- Home
- ChannelUp / ChannelDown
- PlayPause
- VolumeUp / VolumeDown / Mute
- Info
- Guide (Enhanced Guide Mode; optional on Basic Mode remotes)

The application must not require a specific Linux event code to be hard-coded throughout the UI. Device-specific mappings belong in one input/profile layer.

## Display and playback architecture assumptions to prove in Phase 1

- Intel HD Graphics 630 is the reference GPU.
- Playback should use Linux hardware video acceleration where supported.
- The TV experience will own the visible display during normal operation.
- No full desktop environment is required.
- The final presentation/session technology is selected only after hardware-accelerated playback and full-screen output are proven.

## Process supervision

The production runtime will be supervised by systemd. The runtime must be able to restart after an unexpected process failure without exposing a shell or login screen. Exact service boundaries are intentionally deferred to Phase 2, but the Phase 1 appliance proof must demonstrate that systemd supervision can provide the required behaviour.

## Rejected normal-operation approaches

### Conventional desktop environment

Rejected because it increases boot overhead and creates visible desktop/login/cursor failure modes that conflict with the appliance requirement.

### Chromium-only kiosk as the core appliance architecture

Not selected as the default architecture because it couples the complete television runtime to a browser process before the playback/frontend technology has been chosen. Browser technology may still be used for appropriate UI surfaces later if it meets the architecture and performance requirements.

## Design rule

> NostalgiaBox should feel like a television appliance, not a computer. Linux must remain an implementation detail during normal use.