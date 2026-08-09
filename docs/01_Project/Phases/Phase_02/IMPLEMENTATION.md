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

**Implementation status:** complete. Automated Debian 13 validation and isolated real-MPV JSON IPC
control validation passed on the reference Dell. Phase 1 HDMI/ALSA playback remains independently
proven; a concurrent second MPV could not acquire the exclusive busy HDMI ALSA device, as expected.

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

### Implemented Task 2.4 shape

- `application.player` defines the MPV-agnostic `Player` protocol, three-state `PlayerState` and
  controlled player error hierarchy.
- `playback.transport` owns persistent AF_UNIX communication, newline framing, unique request IDs,
  response correlation, queued unsolicited events, timeouts and socket/protocol error translation.
- `playback.mpv` maps the port to structured MPV commands/properties and is the only playback
  position float-seconds conversion boundary.
- `playback.fake` supplies a deterministic state/history fake for Task 2.5 without MPV or clocks.
- `nostalgiabox-mpv-validate` supplies an explicit, database-free manual command for an isolated
  reference-appliance test instance.

The chosen supervision model is separately systemd-supervised core and MPV services, with one
long-running MPV process. The adapter is attach-only. Permanent service units, runtime-directory
ownership and ordering remain deferred; the adapter does not spawn, kill or supervise MPV.

### Acceptance

- adapter can control a real MPV instance on the reference Dell;
- domain/application tests can run with no MPV process;
- MPV process/socket failures become explicit typed errors;
- no code parses human-oriented terminal output as an API.

## Task 2.5 — One-channel runtime proof

**Implementation status:** complete. Automated Debian 13 validation and the isolated live Channel
001 proof passed on the reference Dell, including mid-programme tune, automatic boundary advance,
fresh-process restart/rejoin and continued boundary operation after restart.

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

### Implemented Task 2.5 shape

- `application.runtime.ChannelRuntime` owns initial synchronisation, boundary-only normal ticks,
  forced live resynchronisation, immutable runtime snapshots and explicit runtime failures.
- Application-owned timeline, media-location and channel-lookup protocols keep persistence values
  and SQLAlchemy outside orchestration.
- `persistence.runtime_sources.SqlAlchemyRuntimeDataSource` uses a closed short-lived session for
  each lookup; no session remains open while the player is commanded.
- Structured load logs include action, IDs, UTC resolution/boundary instants and exact target
  offset. Same-entry polls log only at debug level.
- `nostalgiabox-channel-proof` requires explicit database URL, MPV socket and channel number,
  supports `--once` and a configurable continuous poll, and neither migrates/seeds nor launches MPV.
- `GET /runtime` reports the latest injected snapshot or an explicit inactive state. It is
  observation-only; `/health` is unchanged.

No authoritative playback position is persisted. A new runtime and forced resynchronisation both
recompute wall-clock truth using the Task 2.2 resolver. Continuous drift correction, system suspend
hooks, production services and control API endpoints remain deferred.

### Acceptance

On the reference appliance, demonstrate at minimum:

- tune at the start of a programme;
- tune part-way through a programme;
- tune immediately before/after a programme boundary;
- restart the runtime and rejoin the correct current programme/offset;
- advance across at least one programme boundary;
- explicit live re-sync after a period of suspend or simulated clock advancement.

## Task 2.6 — Input proof and failure behaviour

**Implementation status:** complete. Automated Debian 13 validation and all isolated reference-Dell
proofs passed: physical remote mapping, remote-to-real-MPV pause/resume, controlled missing/corrupt
media, bounded player-loss recovery, and same-entry/cross-boundary wall-clock rejoin.

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

### Implemented Task 2.6 shape

- `application.input` defines `InputAction`, `InputOutcome` and the MPV-agnostic application input
  controller.
- `input.profile` contains the dedicated Nordic 1915:1025 Consumer Control profile; changing the
  raw binding does not affect runtime, timeline, persistence or playback command construction.
- `input.linux` lazily loads optional `evdev==1.9.3`, opens an explicit operator path and emits one
  action only for key press.
- `nostalgiabox-input-proof` requires explicit device and MPV socket paths, attaches to both, reports
  mapped actions/results and closes resources on Ctrl+C. It neither uses a database nor owns MPV.
- MPV load confirmation consumes structured `start-file`, `file-loaded` and matching `end-file`
  events behind the playback boundary. `PlayerMediaLoadError` identifies accepted commands whose
  media subsequently fails to load.
- `ChannelRuntime` retains controlled failure state and the original typed cause. Known failed
  media is not retried within the same scheduled entry; a later entry or explicit resync may retry.
- Player health and reconnect attempts use separate five-second bounded cadences. Recovery forces a
  new timeline load and wall-clock resolution before playback is loaded.
- `GET /runtime` remains read-only and adds an optional sanitized failure projection. `/health` is
  unchanged.

Task 2.6 does not add final TV controls, input configuration UI, process supervision, systemd
units, suspend hooks, database migrations, schedule mutation or fallback/skip policy.

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

### Closure result

**Complete — 2026-08-09.** Task 2.7 added a focused migrated seed-to-runtime integration proof,
explicit architecture/dependency checks and a complete requirement-to-evidence audit. Final
reference-Dell validation on Debian 13/Python 3.13.5 passed all 201 tests with no skips, including
AF_UNIX; the 9 Task 2.7 closure tests also passed independently. Ruff lint/format and strict mypy
over 80 source files passed, as did the full temporary SQLite migration lifecycle. No production
code or dependency was changed. See [`TRACEABILITY.md`](TRACEABILITY.md) and
[`TESTING.md`](TESTING.md).

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

**Satisfied — 2026-08-09.** Tasks 2.1 through 2.6 supplied the documented reference-Dell evidence;
Task 2.7 reconciled that evidence with every requirement, added platform-neutral closure tests and
completed its final Debian reference-Dell regression. No Phase 2 blocker remains.
