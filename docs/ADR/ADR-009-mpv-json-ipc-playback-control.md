# ADR-009 — Control MPV through JSON IPC

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

Phase 1 proved MPV playback, Intel VA-API hardware decoding, full-screen video and HDMI audio on the Dell reference appliance. Phase 2 now needs reliable programmatic control without replacing the proven playback engine.

Possible approaches included repeatedly launching MPV with command-line arguments, parsing terminal output, embedding libmpv directly or controlling a long-running MPV process through its supported IPC interface.

## Decision

Keep MPV as the playback engine and control it through MPV JSON IPC over a Unix-domain socket.

Application code interacts with MPV through a NostalgiaBox player interface/adapter. Core scheduling logic must not depend directly on MPV command syntax.

A long-running MPV instance is preferred for the appliance runtime unless integration testing reveals a stronger reason for a different process model.

## Required Phase 2 capabilities

The adapter must support at minimum:

- load media;
- specify or seek to a target playback position;
- pause;
- resume;
- stop;
- query playback time/state;
- detect socket/player loss;
- translate player failures into controlled application errors.

## Rationale

- Reuses the playback engine already proven on the hardware.
- JSON IPC is designed for interactive external control.
- Separates channel scheduling from codec/player implementation.
- A fake player can implement the same application-facing interface for tests.
- Keeping one player process can reduce visible startup/transition overhead later.

## Consequences

### Positive

- No codec or rendering stack needs to be implemented by NostalgiaBox.
- Player control can be unit/integration tested independently.
- MPV can later be upgraded or replaced behind the adapter if necessary.

### Negative

- The runtime must supervise socket/process availability.
- MPV events and asynchronous state changes need careful handling.
- Process ownership between the core and systemd must be documented after the Phase 2 integration proof.

## Constraints

- Do not parse human-readable MPV terminal output as an application API.
- Do not place raw MPV JSON commands throughout domain/application code.
- Preserve the Phase 1 hardware-acceleration/audio configuration in deployment/player configuration.
- On player recovery, the channel timeline remains authoritative; the player must be re-synchronised from wall-clock time.

## Rejected alternatives

### Re-launch MPV for every programme

Simple for a prototype but creates avoidable transition/startup overhead and weakens process/state control.

### Parse stdout/stderr

Rejected because human-readable console output is not a stable machine-control API.

### Implement media playback directly

Rejected because mature MPV/FFmpeg playback already meets the requirement and has been validated on the target GPU/audio path.
