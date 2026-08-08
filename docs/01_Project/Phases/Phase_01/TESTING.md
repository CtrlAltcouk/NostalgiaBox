# Phase 1 — Hardware Validation and Appliance Base: Test Plan

## Test status legend

- `PASS` — demonstrated successfully.
- `FAIL` — requirement not met.
- `PARTIAL` — enough evidence exists to proceed, but additional validation remains.
- `DEFERRED` — explicitly accepted as non-blocking carry-over to a later phase.

## Phase 1 closure status

**Phase 1 accepted complete — 2026-08-08.**

The reference appliance has proven the core hardware, networking, display/audio, hardware-accelerated playback, hidden-startup, input and standby/resume assumptions required to begin Phase 2.

Remaining formal hardware-health, sustained thermal and production-supervision checks are explicitly carried into later implementation/hardening work. They are not considered blockers to the Phase 2 one-channel architecture proof.

## Current status

| Area | Status | Evidence / notes |
| --- | --- | --- |
| Debian 13 minimal install | PASS | Boots successfully without a conventional desktop environment. |
| SSH | PASS | Remote login working independently of the appliance TV session. |
| Wi-Fi | PASS | TP-Link TL-WN823N V2/V3 connected through NetworkManager. |
| DNS after reboot | PASS | `systemd-resolved` installed; `/etc/resolv.conf` linked to the stub resolver; name resolution verified after reboot. |
| Git / repository checkout | PASS | Repository tracking `origin/main` under `/opt/nostalgiabox`. |
| Hardware inventory | PASS | i5-7500, Intel HD 630, 16 GB DDR4, SK hynix SC311 256 GB recorded. |
| USB remote enumeration | PASS | Nordic `1915:1025` composite receiver detected as consumer-control, keyboard and mouse interfaces. |
| USB remote key events | PASS | Core navigation/media controls and `KEY_POWER` verified. Event numbers are treated as unstable by design. |
| Remote standby | PASS | Current remote power button successfully initiates suspend while Linux is awake. |
| Remote wake from S3 | PARTIAL | Dell/USB wake path works with a normal USB keyboard; current Nordic receiver cannot wake the system and must be replaced for final sofa-only power control. |
| SSD health | DEFERRED | Formal SMART record still required before hardened household release. |
| Memory confidence test | DEFERRED | Formal memory confidence test still required before hardened household release. |
| Display output | PASS | Full-screen 1080p playback demonstrated on the target television path. |
| HDMI/DP audio | PASS | HDMI/ALSA playback demonstrated and working with MPV. |
| H.264 hardware decode | PASS | VA-API support detected and full-screen H.264 playback demonstrated using hardware decoding. |
| HEVC capability | PARTIAL | Intel HD 630/VA-API capability detected; final production format policy and representative validation remain to be recorded. |
| Full-screen appliance session | PASS | Automatic `nostalgia` console session launches X/Openbox/MPV without exposing the normal desktop to the TV user. |
| Production process supervision | DEFERRED | Phase 1 startup proof works; final service boundaries and crash-restart supervision are deliberately owned by Phase 2 architecture. |
| Boot timing | PASS | Cold-boot profiling completed; user-visible splash appears at roughly eight seconds on the reference unit. Initramfs optimisation reduced the loader stage materially. |
| Suspend/resume | PASS | `deep`/S3 suspend and resume work; playback returns at the same position. |
| Multi-hour playback / thermals | DEFERRED | Sustained thermal/fan record remains a hardening requirement before release. |

## Remote acceptance tests

1. Receiver enumerates after boot — **PASS**.
2. D-pad produces distinct up/down/left/right actions — **PASS**.
3. Centre/OK produces a select action — **PASS**.
4. Back/Delete-style control produces a back-capable event — **PASS**.
5. Page Up and Page Down can be mapped to Channel Up and Channel Down — **PASS**.
6. Home produces a Home/Live-TV-capable event — **PASS**.
7. Play/Pause produces one logical PlayPause-capable event — **PASS**.
8. Volume Up/Down and Mute produce distinct events — **PASS**.
9. Power produces `KEY_POWER` and can initiate standby — **PASS**.
10. Menu/three-line button is captured and can be assigned later — **PASS for capture; final action deferred**.
11. Mouse/air-mouse input is not required for Basic Mode — **PASS as architecture constraint; production suppression remains to implement**.
12. Remote wake from S3 — **CURRENT RECEIVER LIMITATION**. Keyboard wake proves the Dell/USB path; replacement receiver required.

See [`../../../03_Hardware/REMOTE_CONTROL.md`](../../../03_Hardware/REMOTE_CONTROL.md) for the detailed mapping and wake limitation.

## Video/audio acceptance tests

1. Detect hardware decode capabilities — **PASS**.
2. Play representative 1080p H.264 full-screen with audio — **PASS**.
3. Confirm hardware decode is active — **PASS**.
4. Confirm HDMI audio output works with MPV — **PASS**.
5. Confirm audio remains usable after reboot — **PASS during appliance startup validation**.
6. Representative HEVC/H.265 validation and final support policy — **PARTIAL / carry into Phase 2-3 format policy work**.
7. Long-duration playback and thermal record — **DEFERRED to hardening evidence**.

## Appliance startup acceptance tests

1. Power on does not require keyboard/mouse interaction — **PASS**.
2. Normal TV output does not expose a conventional desktop/taskbar — **PASS**.
3. NostalgiaBox splash appears during startup — **PASS**.
4. Validation playback starts automatically — **PASS**.
5. Reboot returns to the appliance experience — **PASS**.
6. Network reconnects automatically — **PASS**.
7. Safe standby path works — **PASS**.
8. Physical power button can wake from S3 — **PASS**.
9. Compatible USB keyboard can wake from S3 — **PASS** after BIOS power settings were corrected.
10. Current reference remote can wake from S3 — **NO; documented accessory limitation**.
11. Boot timings are recorded and compared — **PASS**.
12. Production service crash recovery — **DEFERRED to Phase 2 once final service boundaries exist**.

## Boot optimisation evidence

Phase 1 boot profiling established that:

- the original initramfs was approximately 112 MB;
- `MODULES=dep` reduced it to approximately 24 MB using Zstd while preserving required hardware modules;
- the measured loader stage improved from roughly 6.9 seconds to roughly 3.8 seconds;
- LZ4 was benchmarked and was slightly slower overall than Zstd on the reference machine;
- `i915.fastboot=1` is unsupported by the installed kernel and was removed;
- initramfs `fastboot` produced a small additional gain but skips the root filesystem check and is not part of the safe baseline configuration;
- cold boot is acceptable as a recovery/maintenance path, while S3 suspend/resume provides the preferred everyday power experience.

## Phase 1 exit decision

No unresolved item is considered to invalidate Phase 2's core architecture and one-channel proof.

Accepted carry-over is limited to work that becomes more meaningful once the production architecture exists or that belongs to release hardening:

- final wake-capable remote/receiver selection;
- production key repeat/debounce and mouse suppression;
- formal SMART and memory-health evidence;
- sustained thermal/fan evidence;
- production process supervision/crash recovery;
- final HEVC/support-format policy.

Phase 2 is approved to begin.