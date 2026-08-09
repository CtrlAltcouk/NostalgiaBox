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

#### Task 2.5 `ChannelRuntime`

The application-layer `ChannelRuntime` joins the existing deterministic resolver to infrastructure
through four injected ports: `Clock`, `Player`, `ChannelTimelineSource` and
`MediaLocationSource`. A separate `ChannelLookup` resolves the operator-facing channel number used
by proof composition. Application code never imports SQLAlchemy repositories, `StoredMediaItem`,
MPV commands, sockets, FastAPI or filesystem probing.

Initial `synchronise(channel_id)` loads the validated timeline, reads the clock once, delegates the
half-open interval and exact-offset calculation to the Task 2.2 resolver, resolves the media path
and calls `Player.load(path, live_offset)`. A fresh runtime has no persisted playback cursor; it
always rejoins from wall-clock time plus the deterministic timeline.

A normal `tick()` resolves wall-clock truth again. It updates diagnostic state but performs no
player call while the same entry remains active. When the entry changes it loads the new path once
at the newly calculated offset. It deliberately does not poll `Player.get_position()` or implement
continuous drift correction. `resynchronise()` reloads timeline data and forces a player load even
when the same entry is still active, providing the explicit restart/resume/recovery foundation
without adding system suspend hooks.

The immutable `RuntimeSnapshot` contains channel ID/number/name, timeline-entry ID, media-item ID,
current UTC instant, entry UTC boundaries, exact `timedelta` live offset and last action. It omits
the media path and every persistence/player-specific object. Missing channel/timeline, media
location and current-time coverage are explicit application failures; `PlayerError` remains typed
and observable.

### MPV adapter

Responsible only for MPV-specific behaviour:

- attaching to one already-running player through a configured Unix-domain socket;
- opening the JSON IPC Unix socket;
- sending JSON IPC commands;
- observing properties/events needed by the core;
- converting MPV failures into typed application errors;
- converting application `timedelta` positions to/from MPV numeric seconds.

The application must not parse MPV terminal output as an API.

#### Task 2.4 player port and JSON IPC boundary

Application orchestration depends on a small `Player` protocol supporting load at an absolute
position, absolute seek, pause, resume, stop/unload, current position, state, health and close.
`PlayerState` is deliberately limited to `IDLE`, `PLAYING` and `PAUSED`. Communication failure is
never represented as idle; it raises a controlled `PlayerUnavailableError`.

The MPV adapter is attach-only. Generic MPV command arrays, property names, JSON, request IDs and
floating-point seconds remain private to playback infrastructure. Paths are supplied by later
application orchestration from the Task 2.3 `StoredMediaItem` boundary. The adapter does not query
persistence, inspect media, run `ffprobe`, or require a path to exist before sending it as a JSON
value.

`timedelta` positions are rejected when negative and converted to numeric seconds only at the MPV
boundary. MPV `time-pos` numbers are rounded to the nearest Python microsecond on return. Loading
uses MPV's structured `loadfile` command with a per-file `start` option; seeking uses explicit
`absolute+exact` semantics. No domain datetime is converted to local time.

The transport keeps one connection while active, frames messages as newline-delimited UTF-8 JSON,
assigns monotonically unique request IDs and correlates responses even when reads are partial,
contain multiple messages, or include responses in a different order. Unsolicited events observed
while waiting for a response are queued separately and can be drained; Task 2.4 deliberately adds
no background event thread or complete asynchronous event framework.

The controlled playback error hierarchy is:

```text
PlayerError
  PlayerUnavailableError  socket missing/refused, broken connection or EOF
  PlayerTimeoutError      command response exceeded configured timeout
  PlayerProtocolError     malformed JSON/response/property data
  PlayerCommandError      MPV returned a non-success command error
```

The default typed connection configuration is `/run/nostalgiabox/mpv.sock` with a two-second
command timeout. Both are configurable through `NOSTALGIABOX_MPV_SOCKET_PATH` and
`NOSTALGIABOX_MPV_COMMAND_TIMEOUT_SECONDS`; automated tests use only fake or temporary paths.
`FakePlayer` implements the same application protocol deterministically, records operation history,
supports one-shot simulated failures and performs no sleeping or clock advancement.

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

#### Task 2.3 schema and conversion boundary

The first migration (`20260808_0001`) creates three tables:

- `media_items(id, title, duration_us, path)` with `duration_us > 0`;
- `channels(id, number, name)` with a positive unique channel number;
- `timeline_entries(id, channel_id, media_item_id, content_kind, start_utc_us,
  end_utc_us)` with foreign keys to channels/media, `end_utc_us > start_utc_us`, unique
  `(channel_id, start_utc_us)` and an ordered lookup index on those columns.

SQLite stores durations and absolute instants as signed `INTEGER` microseconds. Timeline instants
are exact offsets from `1970-01-01T00:00:00Z`; conversion uses integer `datetime`/`timedelta`
arithmetic and never floating-point timestamps. Reconstructed instants are aware UTC values.

`StoredMediaItem` is the persistence-side boundary pairing an approved domain `MediaItem` with a
filesystem path. Paths do not enter the pure domain model and Task 2.3 does not inspect or require
them to exist. Explicit mappers convert ORM records to domain/stored-media values. Unknown content
kinds and corrupt persisted values raise controlled persistence conversion errors.

`MediaRepository`, `ChannelRepository` and `TimelineRepository` accept an explicit SQLAlchemy
session and never commit it. Missing media/channel lookups return `None`; loading a missing channel
or empty timeline raises an explicit not-found error. Timeline loading orders by `start_utc_us` and
constructs `ChannelTimeline`, so domain validation remains authoritative for order, gaps and
overlaps. SQLite engines enable `PRAGMA foreign_keys = ON` on every connection; WAL is not enabled.

Task 2.5 adds `SqlAlchemyRuntimeDataSource`, which implements the application timeline, media-path
and channel-number ports. Every operation creates and closes its own short-lived session. Timeline
and path sessions are closed before `ChannelRuntime` commands the player, so no database transaction
is retained across IPC or playback waits. The adapter translates absent persistent records into
application-level unavailable errors without exposing ORM or `StoredMediaItem` values.

#### Task 2.3 proof seed policy

The proof seed tool consumes an external JSON manifest containing channel identity, aware
`start_utc`, and ordered media objects with `id`, `title`, positive `duration_us` and `path`.
It requires an explicit persistent SQLite `--database-url`, never assumes the production path,
does not inspect media files and does not run migrations. A missing schema instructs the operator
to run `alembic upgrade head`.

Within one caller-owned transaction, the seed operation uses the Task 2.2 sequential builder,
upserts the named channel and supplied media by stable ID, and replaces timeline entries only for
that channel. Reapplying an identical manifest creates no duplicates. Unrelated channels and media
are retained. A channel-number conflict with a different stable channel ID fails explicitly, and
any failed operation rolls back the complete transaction.

### API boundary

FastAPI provides the future-facing local API boundary. Phase 2 should keep the API minimal and oriented toward validation/health rather than prematurely implementing the Phase 3 Web UI.

Task 2.5 exposes only:

- service health;
- `GET /runtime`, a read-only projection of an explicitly injected latest runtime snapshot.

Before initial tune, `/runtime` returns an explicit inactive representation. Route code performs no
scheduling, persistence or player operations. There are no runtime control endpoints in Task 2.5,
and the API remains constructible with no database, MPV process or running `ChannelRuntime`. The
internal domain and application layers do not depend on FastAPI request/response types.

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

#### Task 2.6 logical input boundary

`application.input.InputAction` owns the logical action vocabulary and currently contains only
`PLAY_PAUSE`. `ApplicationInputController` depends solely on the `Player` port: playing becomes
paused, paused becomes playing, and idle is an explicit no-op because input alone must not select
media. Adding later logical actions does not change how Linux events are read.

`input.profile.RemoteProfile` owns physical key mappings. The Phase 2 reference profile is named
`nordic-1915-1025-consumer-control` and maps Linux `KEY_PLAYPAUSE` (164) to logical
`PLAY_PAUSE`. USB identity, raw key values and profile names remain input-infrastructure details.
`input.linux.LinuxInputSource` opens only an operator-supplied path, accepts stable
`/dev/input/by-id/...` paths, translates only EV_KEY press values, and ignores release, repeat,
unknown keys and non-key events. No event-number path is a source-code default.

The adapter imports `python-evdev` lazily. It is pinned as the optional `linux-input` extra, so the
ordinary Windows development installation and all automated tests require neither evdev nor a real
input device.

### Task 2.6 controlled failure and recovery model

`RuntimeFailure` is the application-owned diagnostic state. It retains the original typed
exception internally while the read-only API exposes only category, message, player failure type,
channel/timeline/media IDs and occurrence time. It never exposes paths, ORM values, raw MPV JSON,
Linux events or stack traces. The categories preserve these distinctions:

```text
media_location
media_load
player_unavailable
player_timeout
player_protocol
player_command
```

MPV `loadfile` command success means only that playlist manipulation was accepted. Following the
[official MPV event semantics](https://mpv.io/manual/stable/#list-of-events), the adapter therefore
waits inside playback infrastructure for `start-file`, captures its playlist-entry ID, then waits
for either `file-loaded` or a matching `end-file`. A matching error end event becomes
`PlayerMediaLoadError`; command rejection, socket loss, timeout and malformed IPC remain their
existing distinct types. Only structured JSON IPC events are used.

After a missing location or unplayable-media failure, the runtime records the scheduled entry and
suppresses repeat attempts for that same entry. It neither skips the programme nor alters the
database. An explicit resynchronisation or a later scheduled entry permits a new attempt.

Normal active playback health is checked at most every five seconds. After an infrastructure
failure, health/reconnection is retried at most every five seconds; unchanged waiting is not logged
at info level. The application never spawns, kills or supervises MPV. Once the independently
supervised player is healthy, the runtime reloads the timeline, resolves current wall-clock truth
and loads the entry live now at its recalculated offset, even if a boundary passed while MPV was
absent.

## Minimum domain model

### MediaItem

Implemented Task 2.2 fields:

- `id`
- `title`
- `duration` as an exact Python `timedelta`

Filesystem path/source information belongs to later catalogue and persistence infrastructure, not
the pure Task 2.2 `MediaItem` domain value. The persistence representation of duration is
deliberately deferred to Task 2.3; timeline-domain arithmetic uses `timedelta`.

### Channel

Implemented Task 2.2 fields:

- `id`
- `number`
- `name`

Channel 001 is the only required Phase 2 channel.

Enabled/disabled state may be introduced at the appropriate persistence or application boundary
later. It is not required by the pure Task 2.2 timeline engine.

### TimelineEntry

Implemented Task 2.2 fields:

- `id`
- `channel_id`
- `media_item_id`
- `content_kind`
- `start_utc`
- `end_utc`

`ContentKind` belongs to `TimelineEntry`, allowing the interval model to gain future content kinds
without placing scheduling concerns on `MediaItem`. Task 2.2 implements only `PROGRAMME`.

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

### Task 2.2 domain implementation details

The pure domain engine represents channel timelines as non-empty immutable sequences in the
order supplied by the caller. It does not silently sort entries. A contiguous channel timeline
rejects entries for another channel, chronological misordering, overlaps and gaps with explicit
domain exceptions.

Active-entry intervals are half-open: `start_utc <= now_utc < end_utc`. Resolution returns the
active immutable entry together with an exact `timedelta` live offset. An instant before the first
entry or at/after the final entry raises an explicit timeline-not-covered error; the engine never
chooses a nearest entry.

Sequential proof construction accepts a channel, an absolute start instant and media items in a
specified order. It derives each end from the supplied positive `timedelta` duration and uses that
end as the next start. Entry identifiers are derived deterministically from the channel, UTC start
and sequence position. Construction performs no randomisation, persistence or media-file access.

## Time handling

- Persist absolute instants in UTC.
- Use timezone-aware Python datetimes only.
- Reject naive datetimes at domain boundaries.
- Use an injected `Clock` interface so unit tests can fix time precisely.
- Keep configured local timezone, such as `Europe/London`, for schedule authoring/display boundaries rather than timeline identity.
- Explicitly test DST transitions before Phase 2 closes.

Task 2.2 uses Python `datetime`/`timedelta` microsecond precision throughout. Naive datetimes are
rejected. Aware non-UTC values accepted at public domain boundaries are explicitly normalised with
`astimezone(UTC)` before comparison or storage in immutable domain values. The production
`SystemClock` returns UTC; application orchestration accepts an injected `Clock`, allowing tests to
use a fixed and advanceable fake without timeline functions reading system time directly.

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

Task 2.4 fixes the process-ownership direction:

- systemd will supervise the NostalgiaBox core and MPV separately;
- one long-running, idle-capable MPV instance is preferred;
- the adapter only attaches through the Unix-domain socket and never launches, kills or supervises MPV;
- a new core/adapter instance reconnects through IPC, and a lost MPV connection is reported as a
  typed player-unavailable failure;
- exact service ordering, runtime-directory creation and permanent unit files are deferred to
  production runtime/service integration.

The eventual MPV service configuration owns the Phase 1-proven `--fs`, `--no-border`,
`--hwdec=vaapi`, HDMI/ALSA audio selection, `--input-ipc-server` socket creation and persistent
idle-player flags. None of these process flags belongs in domain or application business logic.

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
