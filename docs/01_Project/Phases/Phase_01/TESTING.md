# Phase 1 — Hardware Validation and Appliance Base: Test Plan

## Test status legend

- `PASS` — demonstrated successfully.
- `FAIL` — requirement not met.
- `BLOCKED` — cannot yet be tested.
- `PARTIAL` — some evidence exists but acceptance is incomplete.

## Current status

| Area | Status | Evidence / notes |
| --- | --- | --- |
| Debian 13 minimal install | PASS | Boots successfully without a desktop environment. |
| SSH | PASS | Remote login working. |
| Wi-Fi | PASS | TP-Link TL-WN823N V2/V3 connected through NetworkManager. |
| DNS after reboot | PASS | `systemd-resolved` installed; `/etc/resolv.conf` linked to stub resolver; name resolution verified after reboot. |
| Git / repository checkout | PASS | Repository tracking `origin/main` under `/opt/nostalgiabox`. |
| Hardware inventory | PASS | i5-7500, Intel HD 630, 16 GB DDR4, SK hynix SC311 256 GB recorded. |
| USB remote enumeration | PASS | Nordic Semiconductor USB composite receiver detected as HID consumer control, keyboard and mouse interfaces. |
| USB remote key events | PARTIAL | Core keys verified; full repeat/replug/persistence test still required. |
| SSD health | BLOCKED | SMART test not yet recorded. |
| Memory confidence test | BLOCKED | Test not yet recorded. |
| Display output | PARTIAL | GPU detected; target display modes still to be validated. |
| HDMI/DP audio | BLOCKED | Playback test not yet recorded. |
| H.264 hardware decode | BLOCKED | VA-API/playback evidence not yet recorded. |
| HEVC capability | BLOCKED | Capability/playback evidence not yet recorded. |
| Full-screen appliance session | BLOCKED | Startup/session technology not yet implemented. |
| systemd crash recovery | BLOCKED | Appliance validation service not yet implemented. |
| Boot timing | BLOCKED | Measurements not yet captured. |
| Multi-hour playback / thermals | BLOCKED | Sustained test not yet run. |

## Remote acceptance tests

1. Receiver enumerates after cold boot.
2. Receiver enumerates after unplug/replug.
3. D-pad produces distinct up/down/left/right actions.
4. Centre/OK produces a select action.
5. Back produces a back action.
6. Page Up and Page Down can be mapped to Channel Up and Channel Down on the reference remote.
7. Home produces a Home/Live-TV action.
8. Play/Pause produces one logical PlayPause action.
9. Volume Up/Down and Mute produce distinct logical actions.
10. Menu/three-line button is captured and can be assigned later (candidate: Info in Basic Mode; Guide/Menu in enhanced mode).
11. Held navigation keys have acceptable repeat behaviour.
12. Mouse/air-mouse events can be ignored/disabled without affecting remote navigation.
13. Remote remains usable after reboot.

## Video/audio acceptance tests

1. Detect hardware decode capabilities.
2. Play H.264 720p full-screen with audio.
3. Play H.264 1080p full-screen with audio.
4. Confirm hardware decode is active.
5. Record CPU load and dropped frames during 1080p playback.
6. Test representative HEVC/H.265 sample and record outcome.
7. Confirm audio device remains available after reboot.
8. Disconnect/reconnect display and confirm recoverable playback/audio behaviour.
9. Run representative video continuously for at least two hours and record temperatures/fan behaviour.

## Appliance startup acceptance tests

1. Power on does not require keyboard/mouse interaction.
2. Normal TV output does not expose desktop, taskbar or shell.
3. NostalgiaBox validation screen/runtime starts automatically.
4. Killing the validation runtime results in automatic systemd restart.
5. Reboot returns to the appliance experience.
6. Network reconnects automatically.
7. Safe shutdown path works.
8. Boot timings are recorded and compared to the target.

## Phase 1 exit review

Before Phase 2 begins, review every `BLOCKED`, `PARTIAL` and `FAIL` entry. No blocker affecting playback, display/audio, remote input, networking, startup supervision or hardware reliability may be carried into Phase 2 without an explicit architecture decision and documented mitigation.