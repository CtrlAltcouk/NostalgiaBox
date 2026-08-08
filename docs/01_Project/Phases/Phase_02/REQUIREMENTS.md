# Phase 2 — Core Architecture and One-Channel Proof: Requirements

## Purpose

Phase 2 proves the highest-risk software assumption in NostalgiaBox before wider product features are built: one channel must behave like a continuously running real-time television channel and must tune to the correct media item at the correct elapsed position.

Phase 2 is a proof of architecture, not a throwaway prototype. Components created here must be suitable foundations for the later media catalogue, administration web UI, multi-channel engine and Basic Mode television experience.

## Scope

Phase 2 must define and prove:

- the core runtime/service boundaries;
- the backend language and application framework;
- the embedded database and migration approach;
- the playback-control boundary around MPV;
- the minimum domain model for media, channel, timeline and playback state;
- deterministic real-time timeline resolution;
- explicit UTC/timezone handling;
- restart/rejoin behaviour;
- an input abstraction suitable for keyboard and USB remote events;
- process supervision expectations for the core runtime and player.

## Functional requirements

### Real-time channel behaviour

1. A test Channel 001 must have a deterministic timeline containing at least two media items with known durations.
2. The channel timeline must advance against wall-clock time even while the channel is not being watched.
3. At tune time, the runtime must identify the timeline entry satisfying `start_utc <= now < end_utc`.
4. The playback offset must equal the elapsed wall-clock duration from the active timeline entry start.
5. The player must open the correct media item and seek to the calculated offset.
6. Restarting the NostalgiaBox runtime must re-resolve the current timeline from the current clock rather than using a stale player position.
7. Returning from appliance suspend must allow the runtime to re-resolve the live channel position rather than assuming the pre-suspend playback position is still authoritative.
8. Programme boundaries must resolve without gaps or overlaps in the valid deterministic test timeline.

### Time model

1. Absolute timeline instants must be represented and persisted in UTC.
2. Local timezone is a presentation/configuration concern and must not be used as an implicit storage format.
3. The reference timezone for development may be `Europe/London`, but the core calculations must remain correct when a different timezone is configured.
4. Clock access must be abstracted so tests can use a fixed/fake clock.
5. Daylight-saving transitions and clock corrections must not cause duplicate or ambiguous absolute timeline entries.

### Playback boundary

1. MPV remains the media playback engine validated in Phase 1.
2. The core application must control MPV through a defined adapter rather than parsing terminal output.
3. The preferred control channel is MPV JSON IPC over a Unix-domain socket.
4. The playback adapter must support at minimum load, seek/start position, pause/resume, stop, current-time query and player-health/state reporting.
5. Core scheduling logic must be testable without launching a real MPV process by using an interface/fake implementation.
6. Hardware decode configuration proven in Phase 1 must remain available on the reference appliance.

### Domain boundaries

The minimum Phase 2 domain must include concepts equivalent to:

- `MediaItem` — stable identity, path/reference, title, duration and content kind;
- `Channel` — identity, channel number, name, enabled state and relevant channel configuration;
- `TimelineEntry` — channel, media reference, content kind, absolute UTC start and end;
- `PlaybackSession` or equivalent runtime state — selected channel, active entry and player state.

The timeline model must not assume every future entry is a programme. A generic content-kind concept must leave room for later idents, adverts, promotions and bumpers without implementing those features in Phase 2.

### Persistence

1. SQLite is the target embedded database for the single-appliance architecture.
2. Schema access must be owned by the core backend process rather than by television or browser UI code.
3. Schema changes must use migrations from the beginning.
4. User/runtime database files must remain outside Git under `/var/lib/nostalgiabox` in production.
5. Tests may use temporary SQLite databases.

### Input abstraction

1. Raw Linux event codes must not be scattered through channel/playback logic.
2. Input adapters must translate physical events into logical actions.
3. Phase 2 only needs enough input to demonstrate the abstraction and basic commands; final TV navigation belongs to later phases.
4. The current Nordic remote remains acceptable for development despite its documented inability to wake the appliance from S3.

### Administration and frontend boundaries

1. The core service must be designed so the Phase 3 administration web UI can communicate with it through a stable API boundary.
2. Phase 2 must not build the full administration web UI.
3. Phase 2 must not commit the product to a heavyweight television UI framework before that framework is required and benchmarked.
4. The full programme guide and Enhanced Guide Mode are explicitly out of scope.

## Non-functional requirements

- Core scheduling calculations must be deterministic and unit-testable.
- Core logic must not require a television, X session or MPV process for unit tests.
- Invalid or missing media must result in explicit domain/playback errors rather than uncontrolled crashes.
- Logging must be structured enough to diagnose which channel entry was selected, which offset was calculated and why playback failed.
- The design must remain local-first and usable without an internet connection.
- Production services must run as the dedicated non-root `nostalgia` identity where practical.

## Explicitly deferred

Phase 2 does not implement:

- full media scanning and matching;
- SMB/NAS source management;
- production administration web UI;
- multiple editable channels;
- advanced scheduling rules;
- channel logos/artwork management;
- a full TV menu or guide;
- adverts, promotions or advanced continuity;
- Plex or Jellyfin integration;
- final remote selection.

## Exit criteria

Phase 2 is complete only when:

- the technology decisions are recorded in accepted ADRs;
- the architecture boundaries are documented;
- one real-time Channel 001 resolves deterministically;
- tuning starts the correct file at the correct wall-clock offset;
- restart/rejoin behaviour is demonstrated;
- boundary, missing-file, timezone and player-failure tests are recorded;
- the implementation is suitable to extend into Phase 3 without a rewrite of the core runtime.
