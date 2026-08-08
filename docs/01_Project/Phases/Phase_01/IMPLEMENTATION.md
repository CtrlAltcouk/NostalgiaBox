# Phase 1 — Hardware Validation and Appliance Base: Implementation Plan

## Status

**Complete — 2026-08-08.**

Phase 1 has demonstrated the Dell OptiPlex 7050 Micro as a viable NostalgiaBox reference appliance and Phase 2 software architecture work is approved to begin.

The Phase 1 implementation deliberately remains a validation/proof configuration. The temporary `startx`/Openbox/MPV launcher will be replaced by production service boundaries during Phase 2 rather than being treated as the final runtime architecture.

## Completed foundation and validation work

### Operating-system and filesystem base

- Debian GNU/Linux 13 (Trixie) minimal installed without a conventional desktop environment.
- SSH remote administration working.
- Git installed and the NostalgiaBox repository checked out under `/opt/nostalgiabox`.
- Dedicated `nostalgia` runtime account created.
- Application, configuration, state, cache and media filesystem boundaries established.
- Local media test storage established at `/srv/nostalgiabox/media/test`.

### Networking

- Wi-Fi working through TP-Link TL-WN823N V2/V3 (RTL8192EU).
- NetworkManager manages network connectivity.
- DNS repaired and made persistent with `systemd-resolved`.
- `/etc/resolv.conf` uses the systemd-resolved stub resolver.
- Networking and DNS survive reboot.

### Reference hardware

- Dell OptiPlex 7050 Micro.
- Intel Core i5-7500, 4 cores / 4 threads.
- Intel HD Graphics 630.
- 16 GB DDR4.
- SK hynix SC311 SATA 256 GB SSD.

### Display, audio and playback

- Intel HD Graphics 630 recognised and driven by `i915`.
- VA-API hardware-decode capability detected.
- Full-screen 1080p H.264 playback demonstrated through MPV using VA-API.
- HDMI audio playback demonstrated and corrected to use the working ALSA/HDMI path.
- Full-screen playback automatically starts on the television output without exposing a normal desktop.
- Representative HEVC capability is supported by the GPU/VA-API stack; production format policy remains a Phase 2/3 decision.

### Appliance startup

The Phase 1 appliance proof now follows this path:

```text
Power on
  -> Dell firmware / UEFI
  -> hidden GRUB/Linux boot
  -> custom NostalgiaBox Plymouth splash
  -> automatic `nostalgia` console session
  -> X.Org + Openbox validation session
  -> full-screen MPV playback
```

Implemented startup work includes:

- automatic console login for the dedicated `nostalgia` account;
- X session automatically starts only on the physical appliance console, not over SSH;
- normal login and X.Org output suppressed from the television experience;
- custom NostalgiaBox Plymouth splash;
- GRUB menu hidden for normal boot;
- mouse cursor hidden and display blanking disabled;
- full-screen playback automatically starts;
- administrator SSH access remains available independently.

The current launcher is intentionally temporary. Phase 2 will define and implement the production backend/player service boundaries and supervision strategy.

### Boot optimisation

Boot profiling was performed with `systemd-analyze`, kernel timing and initramfs tracing.

Key Phase 1 findings:

- the Dell firmware remains a significant fixed part of cold-start time;
- the original generic initramfs was approximately 112 MB;
- changing `initramfs-tools` from `MODULES=most` to `MODULES=dep` reduced the current initramfs to approximately 24 MB with Zstd while retaining the required `i915` module;
- the loader portion of the measured boot fell from roughly 6.9 seconds to roughly 3.8 seconds;
- LZ4 compression was benchmarked and was slightly slower overall than Zstd on the reference hardware, so Zstd remains selected;
- the unsupported `i915.fastboot=1` option was rejected after the kernel reported it as unknown;
- plain initramfs `fastboot` reduced cold-boot time by about one second but skips the root filesystem check, so it is not part of the safe baseline configuration;
- the user-visible NostalgiaBox splash appears at approximately eight seconds during a cold start on the current reference unit.

Cold boot is therefore accepted as a maintenance/recovery path rather than the only normal power experience.

### Standby and resume

Suspend-to-RAM was validated as the preferred everyday standby model:

- `deep` / S3 is supported and selected (`s2idle [deep]`);
- playback resumes at the same position after S3 wake;
- the physical Dell power button can wake the appliance;
- a compatible USB keyboard can wake the appliance from S3 after the required BIOS configuration;
- the current remote power button is recognised as `KEY_POWER` and can put the appliance into standby.

Required Dell BIOS settings established during validation:

- `USB Wake Support`: enabled;
- `Deep Sleep Control`: disabled;
- `Block Sleep (S3 State)`: disabled/unchecked;
- Fast Boot: Minimal;
- Extended POST delay: 0 seconds;
- Full Screen Logo: enabled.

The current Nordic `1915:1025` remote receiver cannot wake the machine from S3. The platform USB wake path is proven by the working keyboard, so this is treated as a receiver limitation. See [`../../../03_Hardware/REMOTE_CONTROL.md`](../../../03_Hardware/REMOTE_CONTROL.md).

## Accepted Phase 1 carry-over

The following items do not block Phase 2 architecture work but must be completed before the first hardened household release:

- formal SSD SMART health record;
- formal memory confidence test;
- sustained multi-hour thermal/fan record;
- production process supervision and crash-restart testing after Phase 2 defines the final service boundaries;
- final remote/receiver selection with S3 wake support;
- production input repeat/debounce behaviour;
- final HEVC/support-format policy.

These items are validation/hardening debt rather than unresolved core architecture assumptions. They must not be forgotten and should be incorporated into Phase 6 hardening/release evidence where they are not naturally completed earlier.

## Phase 1 handoff to Phase 2

Phase 2 begins from a known working appliance platform with:

- stable Debian/networking;
- working display and audio;
- hardware-accelerated full-screen playback;
- hidden appliance startup;
- mapped USB/HID input;
- a proven standby/resume model;
- a documented current-remote wake limitation.

Phase 2 now owns the production application architecture and the one-channel real-time proof. The next work is **not** more boot-shell scripting; it is to define the backend, playback coordinator, domain model and deterministic real-time channel behaviour before production code is written.