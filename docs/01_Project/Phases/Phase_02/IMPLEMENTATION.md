# Phase 2 — Core Architecture and One-Channel Proof: Implementation Plan

## Delivery approach

Phase 2 will be implemented as a sequence of bounded Codex tasks. Each task must leave the repository in a testable state and must update documentation when implementation details materially change.

The goal is not to build all of NostalgiaBox in one task. The goal is to prove the real-time channel model on production-quality foundations that later phases can extend.

## Task 2.1 — Core project skeleton

### Objectives

Create the Python backend foundation without implementing the full channel proof yet.

### Expected work

- Create `backend/pyproject.toml` and a Python 3.13 project/package.
- Establish `src/nostalgiabox/` package boundaries for domain, application, persistence, playback, API, input and configuration.
- Add formatting/lint/type/test tooling appropriate to the chosen stack.
- Add FastAPI application factory and minimal health endpoint.
- Add configuration loading with production-safe defaults and environment overrides.
- Add structured logging foundation suitable for journald/systemd output.
- Add SQLAlchemy 2 engine/session setup.
- Add Alembic migration infrastructure.
- Create the first minimal schema needed for later Phase 2 tasks, or leave migrations empty if the domain model has not yet been approved in code review.
- Add pytest test layout and basic smoke tests.
- Do not add React/TV UI implementation.
- Do not add real media files.

### Acceptance

- project installs into a virtual environment on Debian 13/Python 3.13;
- tests run successfully;
- API health check runs locally;
- package boundaries are clear and no channel/business logic is coupled to FastAPI;
- no runtime database or secret is committed.

## Task 2.2 — Timeline domain engine

### Objectives

Implement the central deterministic scheduling calculation as pure domain/application logic.

### Expected work

- Define domain types for `MediaItem`, `Channel`, `TimelineEntry` and relevant identifiers/value objects.
- Define a `ContentKind` abstraction beginning with programme content while allowing future kinds.
- Define an injectable `Clock` protocol/interface and system/fake implementations.
- Reject naive datetimes at domain boundaries.
- Implement active-entry resolution using `start <= now < end`.
- Implement seek-offset calculation.
- Implement contiguous timeline validation for the proof channel.
- Add deterministic construction/seeding logic for a simple Channel 001 timeline.
- Add comprehensive unit tests around exact boundaries, offsets and invalid timelines.

### Acceptance

- timeline calculations have no dependency on FastAPI, SQLAlchemy, MPV, X11 or filesystem state;
- exact start and end boundaries are covered by tests;
- repeated calls with the same timeline and clock produce identical results;
- timezone-aware UTC behaviour is explicit.

## Task 2.3 — Persistence and seed data

### Objectives

Persist the minimum domain state needed for the one-channel proof.

### Expected work

- Implement SQLAlchemy mappings/repositories without leaking ORM objects into domain logic.
- Add Alembic migration(s) for the approved minimal schema.
- Add development command/script for seeding Channel 001 with user-supplied test media paths and durations.
- Keep production DB path configurable, defaulting toward `/var/lib/nostalgiabox/nostalgiabox.db` in deployment configuration.
- Provide temporary/in-memory or file-backed DB fixtures for tests.

### Acceptance

- a clean database can be migrated from zero;
- seed data can be created repeatably without committing media;
- timeline entries round-trip without losing UTC semantics;
- repository tests cover transaction and lookup behaviour.

## Task 2.4 — MPV JSON IPC adapter

### Objectives

Replace direct shell invocation as the application control model with an explicit player adapter.

### Expected work

- Define a player protocol/interface used by application logic.
- Implement an MPV JSON IPC adapter over a Unix-domain socket.
- Support load/start position, seek, pause/resume, stop, playback time query and health/state observation.
- Support a fake player for unit tests.
- Keep command transport and event parsing isolated from scheduling logic.
- Preserve Phase 1 VA-API/full-screen/audio capability through deployment/player configuration rather than hard-coded domain logic.
- Determine and document whether the core owns MPV directly or whether a separate supervised MPV service is cleaner.

### Acceptance

- adapter can control a real MPV instance on the reference Dell;
- domain/application tests can run with no MPV process;
- MPV process/socket failures become explicit typed errors;
- no code parses human-oriented terminal output as an API.

## Task 2.5 — One-channel runtime proof

### Objectives

Join persistence, timeline resolution and player control to demonstrate the central NostalgiaBox behaviour.

### Expected work

- Load Channel 001 and its timeline.
- Resolve the active entry from the injected/system clock.
- Calculate the correct live offset.
- Command MPV to load the correct item at that offset.
- Re-resolve and re-sync on application restart.
- Provide an explicit re-sync application command suitable for suspend/resume integration.
- Expose minimal development/health API state for observing the selected entry and calculated offset.
- Log channel ID, timeline-entry ID, now/start/end times and target seek offset for diagnostics.

### Acceptance

On the reference appliance, demonstrate at minimum:

- tune at the start of a programme;
- tune part-way through a programme;
- tune immediately before/after a programme boundary;
- restart the runtime and rejoin the correct current programme/offset;
- advance across at least one programme boundary;
- explicit live re-sync after a period of suspend or simulated clock advancement.

## Task 2.6 — Input proof and failure behaviour

### Objectives

Prove the input abstraction and core failure paths without building the final TV interface.

### Expected work

- Define logical input actions needed for the proof.
- Implement a Linux keyboard/evdev adapter or a small reference adapter for the existing remote.
- Keep the raw event-code map in a device/profile boundary.
- Demonstrate at least one playback action through the abstraction.
- Test missing media, corrupt/unplayable media and MPV process failure.
- Ensure failures produce structured logs and controlled application state.

### Acceptance

- changing the physical key mapping does not require editing timeline/playback business logic;
- missing/corrupt media does not crash the whole core process unexpectedly;
- player process loss is detectable and recoverable/retryable according to the documented proof policy.

## Task 2.7 — Phase 2 validation and closure

### Objectives

Run the complete Phase 2 test matrix, reconcile documentation with the actual implementation and decide whether Phase 3 can begin.

### Outputs

- completed `TESTING.md` evidence;
- finalised process-supervision decision;
- updated architecture/component diagrams if implementation changed them;
- recorded dependency/runtime versions;
- any new risks or follow-up issues;
- Phase 2 completion update in the roadmap.

## Implementation rules for Codex tasks

- Read the repository and relevant ADRs before changing code.
- Do not broaden a task into later-phase features.
- Prefer small interfaces and pure domain functions over cross-layer shortcuts.
- Add tests with every behaviour change.
- Do not commit user media, local databases, secrets or machine-specific credentials.
- Do not hard-code `/dev/input/eventN` values.
- Do not make the WebUI or TV UI responsible for schedule calculations.
- Do not replace MPV or the Phase 1 appliance base without an explicit ADR/review.
- Report assumptions and blockers rather than silently inventing product behaviour.

## Phase 2 completion gate

Implementation work can only be considered complete when the proof runs on the real Dell reference appliance, not only in automated tests or a developer workstation.
