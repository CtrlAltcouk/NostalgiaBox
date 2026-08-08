# Phase 2 — Core Architecture and One-Channel Proof

## Architecture status

This document defines the Phase 2 target architecture approved for implementation. It is intentionally small enough to prove the real-time channel model without creating throwaway code.

## Technology baseline

- Core language: Python 3.13
- API/application framework: FastAPI with Pydantic models at external boundaries
- Persistence: SQLite with SQLAlchemy 2 and Alembic migrations
- Playback engine: MPV
- Playback control: MPV JSON IPC over a Unix-domain socket
- Tests: pytest with fake clock and fake player implementations
- Administration UI: React + TypeScript + Vite beginning in Phase 3
- TV UI framework: deliberately not fixed in Phase 2; prove the core with MPV presentation and lightweight overlays first

Each technology choice is documented separately in an ADR.

## Core architectural rule

The NostalgiaBox core service is the single source of truth for channel state, timeline resolution and persistent domain state.

Neither the administration web UI nor the television presentation may independently decide what should be playing.

```text
                          Browser / Phase 3 Web UI
                                   |
                                   | API
                                   v
Remote/Input Adapter ---> NostalgiaBox Core <--- TV presentation
                                   |
                   +---------------+---------------+
                   |               |               |
                   v               v               v
              SQLite DB      Timeline Engine   Playback Coordinator
                                                   |
                                                   | JSON IPC
                                                   v
                                                  MPV
                                                   |
                                                   v
                                                HDMI/TV
```

## Component boundaries

### Core application/service

Responsible for:

- application lifecycle;
- configuration loading;
- database ownership;
- channel selection state;
- orchestration between timeline resolution and playback;
- API boundary for future administration clients;
- logging and health state.

It must not contain codec/rendering implementations.

### Timeline domain engine

Responsible for pure deterministic calculations:

- timeline construction for the Phase 2 seeded test channel;
- resolving the active entry for an absolute instant;
- resolving current/next entries;
- calculating seek offset;
- validating gaps, overlaps and invalid durations.

The engine must depend on domain values and an injected clock, not on MPV, HTTP, X11 or systemd.

### Playback coordinator

Responsible for translating domain playback intent into player operations:

- load the resolved media item;
- start/seek to the live offset;
- pause/resume;
- observe player state;
- handle player process loss;
- request a live resynchronisation after restart/resume when required.

The coordinator consumes a playback interface. The MPV adapter is one implementation; tests use a fake.

### MPV adapter

Responsible only for MPV-specific behaviour:

- starting/attaching to the player process according to the selected supervision design;
- opening the JSON IPC Unix socket;
- sending JSON IPC commands;
- observing properties/events needed by the core;
- converting MPV failures into typed application errors;
- applying the proven Phase 1 hardware decode/audio configuration.

The application must not parse MPV terminal output as an API.

### Persistence layer

Responsible for:

- SQLAlchemy models/repositories;
- transaction boundaries;
- Alembic migrations;
- converting persistence records into domain models;
- preventing SQLite details from leaking into scheduling logic.

Production database location:

```text
/var/lib/nostalgiabox/nostalgiabox.db
```

### API boundary

FastAPI provides the future-facing local API boundary. Phase 2 should keep the API minimal and oriented toward validation/health rather than prematurely implementing the Phase 3 Web UI.

Potential proof endpoints may expose:

- service health;
- current channel/timeline resolution;
- current playback state;
- explicit tune/re-sync command for development.

The internal domain must not depend on FastAPI request/response types.

### Input adapter

Physical Linux input is translated to logical actions before reaching the core.

```text
Linux evdev / keyboard / remote
            |
            v
       Input profile
            |
            v
     LogicalAction enum
            |
            v
     Core command handler
```

The existing Phase 1 reference remote profile remains development input. A replacement wake-capable remote can be added later without changing the core command model.

## Minimum domain model

### MediaItem

Suggested Phase 2 fields:

- `id`
- `path`
- `title`
- `duration_ms`
- `content_kind`

`path` is acceptable for seeded Phase 2 media. Phase 3 replaces manual seeding with catalogue-owned stable media records and source management.

### Channel

Suggested fields:

- `id`
- `number`
- `name`
- `enabled`

Channel 001 is the only required Phase 2 channel.

### TimelineEntry

Suggested fields:

- `id`
- `channel_id`
- `media_item_id`
- `content_kind`
- `start_utc`
- `end_utc`

Invariant:

```text
start_utc < end_utc
```

For a valid contiguous channel proof, adjacent entries satisfy:

```text
entry[n].end_utc == entry[n+1].start_utc
```

### PlaybackSession

Runtime/persistent fields should be kept minimal. It may represent:

- selected channel;
- active timeline-entry identity;
- player state;
- whether playback is currently locally paused;
- last successful synchronisation time.

The authoritative live position is never derived solely from stale persisted player position.

## Real-time timeline algorithm

Timeline entries store absolute UTC instants.

For current absolute time `now_utc`, the active entry is the unique entry satisfying:

```text
entry.start_utc <= now_utc < entry.end_utc
```

The required player seek offset is:

```text
offset = now_utc - entry.start_utc
```

Example:

```text
16:00:00  Episode A starts
16:22:00  Episode B starts
16:44:00  Episode C starts

Current time = 16:31:30
Active entry = Episode B
Seek offset = 00:09:30
```

No playlist cursor is the source of truth. Wall-clock time plus the deterministic channel timeline is authoritative.

## Time handling

- Persist absolute instants in UTC.
- Use timezone-aware Python datetimes only.
- Reject naive datetimes at domain boundaries.
- Use an injected `Clock` interface so unit tests can fix time precisely.
- Keep configured local timezone, such as `Europe/London`, for schedule authoring/display boundaries rather than timeline identity.
- Explicitly test DST transitions before Phase 2 closes.

## Restart and suspend behaviour

### Runtime restart

1. Start core service.
2. Load channel/timeline state.
3. Read current UTC time through the clock abstraction.
4. Resolve active Channel 001 entry.
5. Calculate live offset.
6. Command player to load/seek.

### Resume from suspend

The operating system may resume MPV at its frozen pre-suspend frame. That position is not automatically considered live.

The application must have a resynchronisation path that recalculates current channel entry and live offset after resume. The exact systemd sleep-hook integration may be completed when the production runtime service is introduced, but the Phase 2 core must make re-sync an explicit operation.

## Player supervision direction

Production supervision should use systemd. Phase 2 should keep process ownership explicit:

- the NostalgiaBox core is a supervised service;
- MPV is either started and owned by the core or placed behind a clearly defined supervised player service;
- one long-running MPV instance is preferred to repeatedly launching a new player for each programme transition;
- player death must be detectable and recoverable without corrupting schedule state.

The final service split should be validated during the MPV-adapter task and then documented before Phase 2 exit.

## Frontend strategy

### Administration UI

Phase 3 will use a browser-based administration UI backed by the same core API. React + TypeScript + Vite is the preferred stack.

### Television presentation

Phase 2 deliberately avoids selecting Chromium/Electron/Qt/etc. as the permanent TV shell. Basic proof presentation can use MPV and lightweight overlays. The richer TV UI framework should be selected only when its requirements are concrete and after it is benchmarked on the Dell.

This prevents an unnecessary frontend framework from becoming a dependency of the core real-time proof.

## Data and repository boundaries

Production/runtime state stays outside Git:

```text
/opt/nostalgiabox       application checkout/runtime assets
/etc/nostalgiabox       machine configuration
/var/lib/nostalgiabox   SQLite database and persistent generated state
/var/cache/nostalgiabox rebuildable cache
/srv/nostalgiabox/media user/test media
```

Copyrighted user media must never be added to the repository.

## Phase 2 implementation shape

A target Python package layout should approximately separate:

```text
backend/
  pyproject.toml
  src/nostalgiabox/
    api/
    application/
    domain/
    persistence/
    playback/
    input/
    config/
  tests/
    unit/
    integration/
```

Exact file names may change during implementation, but domain logic must remain isolated from infrastructure adapters.

## Architecture principles for later phases

- one authoritative core backend;
- APIs and UIs consume core behaviour rather than duplicate it;
- timeline generation is separate from real-time playback coordination;
- playback engine is replaceable behind an adapter, even though MPV is the accepted implementation;
- raw remote events are replaceable behind input profiles;
- database migrations exist from the first schema;
- future continuity content extends generic timeline entries rather than forcing a new scheduler architecture.
