# ADR-011 — Separate the administration WebUI from the television UI framework decision

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

NostalgiaBox requires a local browser-based administration interface, while the television experience must be fast, appliance-like and remote-controlled. These surfaces have different requirements.

The Phase 2 delivery plan requires frontend technology choices, but selecting a permanent television framework before the core real-time proof would add an unnecessary dependency and could bias the architecture toward Chromium/Electron/Qt/etc. before their startup, rendering and remote-focus behaviour are measured on the reference Dell.

## Decision

Treat the administration WebUI and television presentation as separate clients of one authoritative core backend.

For the administration WebUI beginning in Phase 3, use React + TypeScript + Vite unless implementation evidence requires a later ADR revision.

Do not select a permanent television UI framework in Phase 2. Use MPV/full-screen proof presentation and lightweight overlays sufficient to validate the channel runtime. Select the richer TV UI technology only when Phase 5/7 requirements are concrete and candidates can be benchmarked on the appliance.

## Rationale

- Avoids making a browser runtime part of the critical playback proof without need.
- Preserves the very lightweight appliance startup established in Phase 1.
- Lets the WebUI use a conventional productive web stack without forcing the same technology onto the TV surface.
- Ensures both UIs consume one backend rather than duplicating timeline/channel logic.

## Consequences

### Positive

- Core architecture remains independent of presentation technology.
- Phase 2 stays focused on the highest-risk real-time scheduling/playback behaviour.
- The WebUI can progress in Phase 3 without waiting for the final TV shell decision.
- Future TV frameworks can be compared using real performance requirements.

### Negative

- The repository may contain two frontend technologies later.
- Shared visual components between WebUI and TV UI cannot be assumed.
- A later ADR will still be required for the production TV presentation framework.

## Interface rule

Both frontend surfaces communicate with the NostalgiaBox core through stable application/API boundaries. Neither frontend may directly own or duplicate authoritative timeline calculations or database writes.

## Deferred TV framework candidates

Candidates such as lightweight native UI, browser kiosk, Qt/QML or other frameworks may be evaluated later. No candidate is accepted by this ADR.
