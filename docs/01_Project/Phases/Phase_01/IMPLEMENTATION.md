# Phase 1 — Hardware Validation and Appliance Base: Implementation Plan

## Completed foundation work

- Debian GNU/Linux 13 (Trixie) minimal installed without a desktop environment.
- SSH remote administration working.
- Wi-Fi working through TP-Link TL-WN823N V2/V3 (RTL8192EU).
- NetworkManager active.
- DNS repaired and made persistent with `systemd-resolved`.
- Git installed.
- NostalgiaBox repository checked out under `/opt/nostalgiabox`.
- Dedicated `nostalgia` service account created.
- Persistent-data, cache and media filesystem boundaries established.
- CPU, RAM, storage and graphics inventory captured.

## Remaining implementation sequence

### 1. Storage and memory health

- Run SMART health checks for the SK hynix SSD.
- Run a memory test or equivalent confidence check on the 16 GB RAM configuration.
- Record SSD wear/health indicators and any errors.

### 2. Thermal and cooling baseline

- Record idle CPU temperature.
- Play representative video and record sustained temperature/fan behaviour.
- Confirm the Dell blower, heatsink and airflow path are operating normally before custom enclosure work begins.

### 3. Remote validation

- Record the reference USB receiver USB ID and all exposed input interfaces.
- Capture `evtest` results for every relevant physical button.
- Define the reference logical action map.
- Verify press/release and held-key repeat behaviour.
- Confirm the air-mouse interface can be ignored or disabled without breaking keyboard/media controls.
- Test operation after reboot and receiver replug.

### 4. Display and audio

- Confirm available DRM/display outputs.
- Confirm target 1080p resolution and refresh rate.
- Confirm HDMI/DisplayPort audio device and playback.
- Verify audio survives reboot and display reconnect.

### 5. Hardware-accelerated playback

- Install the minimum tools required to inspect VA-API support.
- Record supported decode profiles.
- Transfer legal test media into `/srv/nostalgiabox/media/test` using SFTP or another secure transfer method.
- Test H.264 720p and 1080p.
- Test representative HEVC/H.265 content to document actual capability.
- Confirm hardware decode is in use rather than relying only on low CPU usage assumptions.
- Test full-screen playback and audio sync.

### 6. Appliance startup proof

- Create a minimal full-screen Phase 1 validation program/presentation only after the display/session method is selected.
- Configure the `nostalgia` runtime identity.
- Configure systemd startup and supervision.
- Hide normal login/desktop surfaces from the intended TV output.
- Verify automatic restart after deliberately terminating the validation process.
- Define safe shutdown and restart behaviour.

### 7. Boot and recovery measurements

Record at minimum:

- power button to firmware completion where measurable;
- firmware/bootloader to Linux userspace;
- Linux userspace to visible NostalgiaBox validation screen;
- warm reboot time;
- process-crash recovery time;
- Wi-Fi reconnection time after reboot.

### 8. Documentation and Phase 1 review

- Update delivered hardware record.
- Update remote compatibility record.
- Record Debian/networking setup steps, including the DNS issue and permanent resolution.
- Record playback acceleration results.
- Record boot timings and limitations.
- Complete the Phase 1 test plan.
- Review unresolved risks before approving Phase 2.

## Deliberately deferred

The following are not Phase 1 implementation work:

- real-time channel timeline engine;
- media catalogue/database;
- production TV UI;
- administration web UI;
- Enhanced Guide Mode;
- adverts/continuity.

Phase 1 proves the appliance platform. Phase 2 begins application architecture and the one-channel proof only after this foundation passes.