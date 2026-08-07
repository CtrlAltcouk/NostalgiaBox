# ADR-006 — Dedicated Appliance Startup

- **Status:** Accepted
- **Date:** 2026-08-07

## Context

NostalgiaBox is intended to feel like a standalone television appliance. A conventional Linux desktop, graphical login screen, visible terminal, taskbar or mouse cursor would break that experience and introduce additional boot-time and recovery surfaces.

Three broad approaches were considered:

1. Debian with automatic appliance startup and no conventional desktop in normal operation.
2. Debian desktop environment with the application auto-launched.
3. Browser/Chromium kiosk as the primary appliance runtime.

## Decision

Use a dedicated appliance startup model on Debian 13:

```text
Power on
  -> firmware / UEFI
  -> Debian
  -> systemd
  -> NostalgiaBox runtime/session
  -> full-screen NostalgiaBox experience
```

The NostalgiaBox runtime will run under a dedicated non-root identity and will be supervised by systemd. During normal operation the user must not need to interact with Debian itself.

The final display/session/frontend technology is deliberately not selected by this ADR; it will be chosen after Phase 1 playback/display validation and Phase 2 architecture work. The decision here is the appliance behaviour and supervision model, not a commitment to a particular UI toolkit.

## Consequences

### Positive

- Supports the product principle that NostalgiaBox should feel like a television rather than a PC.
- Reduces unnecessary desktop services and visible failure modes.
- Gives systemd responsibility for process startup and recovery.
- Provides a clear separation between administrator maintenance and normal household use.

### Trade-offs

- Display/session setup must be engineered explicitly rather than relying on a full desktop environment.
- Recovery and maintenance access must be designed carefully so failures do not expose a shell on the television.
- Boot optimisation must account for firmware time as well as Linux/application startup.

## Rejected alternatives

### Conventional desktop environment

Rejected for normal operation because it increases overhead and can expose desktop/login/cursor elements during boot, crashes or updates.

### Chromium kiosk as the architectural default

Not selected at this stage because it would prematurely couple the entire television runtime to a browser before playback and frontend technology decisions are validated. Browser technology remains available for appropriate components later, especially the administration web UI.

## Validation required

Phase 1 must demonstrate:

- automatic full-screen startup without manual keyboard/mouse interaction;
- systemd-supervised restart after a deliberately terminated validation process;
- hidden Linux surfaces during normal startup/recovery;
- safe reboot/shutdown behaviour;
- measured cold-boot and recovery timings.