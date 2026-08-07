# Phase 1 — Hardware Validation and Appliance Base: Requirements

## Purpose

Phase 1 turns the reference Dell OptiPlex 7050 Micro into a known-good, repeatable NostalgiaBox appliance platform. Phase 1 is not complete simply because Debian boots; the hardware, networking, display/audio path, remote input, playback acceleration, appliance startup and recovery behaviour must all be demonstrated and documented.

## Confirmed reference platform

- Dell OptiPlex 7050 Micro
- Intel Core i5-7500, 4 cores / 4 threads
- Intel HD Graphics 630
- 16 GB DDR4 (2 × 8 GB), operating at 2400 MT/s
- SK hynix SC311 SATA 256 GB SSD
- Debian GNU/Linux 13 (Trixie), minimal installation
- NetworkManager for network management
- systemd-resolved for DNS resolution
- SSH for administrator maintenance access

## Functional requirements

### Hardware and operating system

1. Debian 13 must install and boot without a desktop environment.
2. The final appliance must use a non-root runtime/service account.
3. Administrator SSH access must be available for development and maintenance without being exposed in the normal television experience.
4. Wi-Fi and Ethernet must be supportable; the current development unit uses a TP-Link TL-WN823N V2/V3 USB Wi-Fi adapter (RTL8192EU).
5. DNS must remain functional across reboot and network reconnection.
6. The SSD, RAM, CPU, fan and thermal behaviour must be validated before Phase 1 closes.

### Display, audio and playback

1. Intel HD Graphics 630 must be recognised by Debian.
2. 1080p output must be stable on the target television/display path.
3. HDMI/DisplayPort audio must work and survive reboot.
4. Hardware-accelerated H.264 playback must be demonstrated.
5. H.265/HEVC capability must be measured and documented rather than assumed.
6. A representative test video must play full-screen without visible Linux desktop components.

### Remote input

1. A simple USB remote must be usable as the primary Basic Mode control device.
2. The application architecture must consume logical actions rather than hard-code one remote model.
3. At minimum Basic Mode requires logical actions for navigation, select, back, channel up/down, play/pause, volume up/down and mute.
4. Extra remote functions may be ignored safely.
5. Mouse/air-mouse behaviour must not be required for normal operation and may be disabled/ignored by the TV interface.
6. Input mappings and Linux event codes must be documented for the reference remote.

### Appliance startup

1. NostalgiaBox must use the dedicated appliance startup approach: Debian boots, the NostalgiaBox runtime starts automatically, and the TV experience takes full-screen control.
2. A general-purpose desktop environment must not be part of normal operation.
3. Users must not normally see a login prompt, terminal, desktop, taskbar or mouse cursor.
4. systemd must supervise the NostalgiaBox runtime and restart it after unexpected failure.
5. Safe shutdown/restart behaviour must be defined before Phase 1 closes.
6. Cold-boot and reboot timings must be measured. The long-term target is under five seconds where hardware/firmware permits; measured reality takes precedence over the target.

## Phase 1 completion gate

Phase 1 may close only when all of the following are evidenced:

- hardware inventory recorded;
- RAM and SSD checks passed;
- stable networking and DNS across reboot;
- reference remote input verified;
- display and audio verified;
- hardware-accelerated video playback verified;
- appliance startup path demonstrated;
- crash recovery/supervision demonstrated;
- boot timings recorded;
- repeatable installation/setup notes updated;
- Phase 1 test report completed with no unresolved blocker that would invalidate Phase 2.