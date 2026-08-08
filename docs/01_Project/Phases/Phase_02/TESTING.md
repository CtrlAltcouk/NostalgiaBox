# Phase 2 — Core Architecture and One-Channel Proof: Test Plan

## Test status legend

- `PASS` — demonstrated successfully.
- `FAIL` — requirement not met.
- `BLOCKED` — cannot yet be tested.
- `PARTIAL` — some evidence exists but acceptance is incomplete.

## Current status

| Area | Status | Evidence / notes |
| --- | --- | --- |
| Technology ADRs | PASS | ADR-007 through ADR-011 accepted for Python/FastAPI, SQLite, MPV JSON IPC, UTC time handling and frontend separation. |
| Python backend skeleton | PASS | Task 2.1 validated on the reference Debian 13 appliance with Python 3.13.5: package installation succeeded, pytest passed 11 tests, Ruff lint/format passed, mypy strict passed, Alembic current/upgrade head passed, and the live `/health` probe returned HTTP 200 with the expected service response. |
| SQLite/Alembic migration path | PASS | Task 2.3 initial migration passed empty upgrade, repeated upgrade, downgrade and re-upgrade tests on temporary SQLite databases. Exact codecs, constraints, foreign keys and repository round trips are covered. |
| Pure timeline domain engine | PASS | Task 2.2 automated validation passed: immutable domain values, contiguous timeline validation, half-open active-entry resolution and exact live offsets are covered by the unit suite. |
| Fake clock / deterministic time tests | PASS | Task 2.2 fixed/repeated resolution and explicit clock advancement across a boundary passed. `SystemClock` returns aware UTC. |
| Automated MPV JSON IPC adapter | PASS | Task 2.4 automated tests cover command mapping, framing, correlation, events, timeouts, EOF, malformed data, command failures, state/position and clean close without a real MPV process. |
| Reference-Dell MPV JSON IPC/control validation | PASS | Task 2.4 controlled a real MPV instance through `/tmp/nostalgiabox-mpv-test.sock`: health, load at a non-zero start, fullscreen VA-API playback, playing/position queries, visible pause/resume, absolute seek, stop and return to idle all passed. Phase 1 HDMI/ALSA capability remains independently proven; concurrent second-MPV HDMI acquisition is not required. |
| Fake player adapter | PASS | Deterministic Player-protocol fake covers exact load/seek positions, state transitions, history and simulated typed failure. |
| Channel 001 seed timeline | PASS | Task 2.3 validated external manifest parsing, deterministic persistence, idempotent re-seeding, target-only replacement and transaction rollback. No media is committed or inspected. |
| Automated one-channel runtime orchestration | PASS | Task 2.5 initial tune, exact boundaries, boundary-only loads, successive entries, forced resync, explicit failures, snapshots and structured logging pass with FakeClock/FakePlayer. |
| SQLite-to-FakePlayer runtime integration | PASS | An Alembic-migrated temporary file-backed SQLite database is seeded, resolved through the real short-session persistence adapter and loads the correct path/offset into FakePlayer. |
| Reference-Dell live Channel 001 proof | PARTIAL | Exact isolated database/socket/manifest instructions are documented; mid-programme tune, live boundary advancement and runtime restart/rejoin have not yet been executed on the Dell. |
| Correct mid-programme tune offset | PARTIAL | Exact application runtime load/offset tests pass; the combined real Channel 001 proof remains pending on the Dell. |
| Restart/rejoin behaviour | PARTIAL | Fresh-runtime FakeClock tests prove no persisted cursor is needed; real proof-runtime restart/rejoin remains pending on the Dell. |
| Suspend/live re-sync path | PARTIAL | Forced same-entry and crossed-boundary resynchronisation pass with simulated lost time. Actual suspend hooks are deliberately not implemented; Dell proof remains. |
| Input abstraction proof | BLOCKED | Not yet implemented. |
| Missing/corrupt media handling | BLOCKED | Not yet implemented. |
| Player failure handling | BLOCKED | Not yet implemented. |
| Timezone/DST tests | PARTIAL | Task 2.2 UTC resolution passed representative `Europe/London` spring-forward and autumn-fold cases. Local schedule authoring and full Phase 2 integration evidence remain. |

### Task 2.2 automated evidence

The Python 3.13 development suite passed 45 tests: all 11 Task 2.1 tests plus 34 Task 2.2
domain/application tests. Task 2.2 coverage includes exact starts, mid-entry offsets, one
microsecond before a boundary, exact half-open boundaries, before/after coverage errors, naive
datetime rejection, aware non-UTC normalisation, media/channel invariants, non-positive durations,
gaps, overlaps, invalid order, channel isolation, deterministic sequential construction,
fake-clock advancement and UTC DST resolution. Ruff lint/format and strict mypy validation also
passed during Task 2.2 development.

### Task 2.3 automated evidence

The Python 3.13 development suite passed 71 tests: all 45 Task 2.1/2.2 tests plus 26 Task 2.3
persistence and seed tests. Evidence covers exact signed epoch/duration microsecond codecs, aware
UTC reconstruction, ORM/domain/path round trips, ordered `ChannelTimeline` reconstruction,
missing lookup behavior, duplicate channel-number rejection, SQLite foreign-key enforcement,
unknown content kinds, corrupt persisted durations/boundaries, full initial-migration lifecycle,
manifest validation, idempotent seed replacement, channel isolation, schema safety and rollback.
All databases and manifests used by automated tests are temporary and never target
`/var/lib/nostalgiabox`.

### Task 2.4 automated evidence

The Windows Python 3.13 development suite passes 130 tests with one AF_UNIX integration test skipped
because that development environment does not expose AF_UNIX. The 59 new passing tests cover the
Player protocol and fake,
non-zero exact positions, negative-position rejection, both conversion directions, awkward Unicode
paths, structured MPV operations, request-ID uniqueness/correlation, partial and multiple-message
framing, interleaved events and responses, malformed JSON/structures/properties, EOF/missing socket,
timeouts, MPV command errors, idle/playing/paused mapping, health and clean connection release. The
platform-gated test exercises the same transport against a temporary real AF_UNIX fake server on a
supporting platform. No automated test connects to `/run/nostalgiabox/mpv.sock` or requires MPV.

Reference Debian 13 automated validation then passed all 131 tests under Python 3.13.5, including
the AF_UNIX integration test skipped on Windows. `ruff check .`, `ruff format --check .` and strict
`mypy` all passed; mypy checked 58 source files.

### Task 2.4 isolated reference-Dell validation

Task 2.4 real-MPV JSON IPC/control acceptance is **PASS** on the reference Debian 13 Dell. The
manual validator connected through `/tmp/nostalgiabox-mpv-test.sock` and used an existing
operator-owned test video. It successfully demonstrated:

- IPC health and a real Unix-domain-socket connection;
- `loadfile` through JSON IPC at a non-zero start position;
- real fullscreen video output using VA-API;
- playing-state and real playback-position queries;
- visible pause and resume on the television;
- absolute seek;
- stop and return to MPV idle state.

The validator reported successful state/position information and every visible control operation
behaved correctly on the television.

#### Audio evidence and concurrent-player limitation

Phase 1 already independently proved working HDMI/ALSA audio through MPV on this Dell. The initial
isolated Task 2.4 second MPV was deliberately launched with `--no-audio` so it would not compete with
the still-running Phase 1 player.

A follow-up test forced the isolated second MPV to use `--ao=alsa`. MPV reported:

```text
[ao/alsa] Playback open error: Device or resource busy
[ao] Failed to initialize audio driver 'alsa'
Could not open/initialize audio device -> no sound.
```

The existing Phase 1 MPV held the exclusive HDMI ALSA device. An earlier unrestricted second-player
test encountered the same ALSA device-busy condition, fell back to sndio and produced audio through
the PC speaker. This is the expected limitation of running two concurrent MPV processes against
the exclusive HDMI device, not a Task 2.4 adapter failure and not the production architecture.

The approved production architecture uses one separately supervised persistent MPV instance. This
evidence does not claim that two concurrent MPV processes can share HDMI audio. Phase 2 remains in
progress because later Phase 2 tasks and the one-channel runtime proof are still outstanding.

### Task 2.5 automated evidence

The Windows Python 3.13 development suite passes 161 tests with the existing AF_UNIX integration
test skipped because that environment does not expose AF_UNIX. The 31 new passing tests cover
initial tune at start/mid-entry, exact microsecond boundaries, same-entry no-load ticks, successive
boundary loads, fresh-runtime restart/rejoin, forced resync within/across entries, unavailable
timeline/media/coverage, observable typed player failure, exact snapshots, structured JSON log
context, explicit CLI targets/in-memory rejection/once/Ctrl+C behavior, channel-number lookup,
Alembic-migrated file-backed SQLite through the real persistence adapter into FakePlayer, inactive
and active `/runtime` responses, route layering and unchanged `/health` behavior. Ruff lint/format
and strict mypy pass. No automated Task 2.5 test requires MPV or real-time sleeping.

### Task 2.5 isolated reference-Dell validation (pending)

Do not mark the live Channel 001 proof PASS until this procedure is executed and results recorded.
It uses only isolated resources:

```text
Database: /tmp/nostalgiabox-phase25.db
Manifest: /tmp/nostalgiabox-phase25.json
MPV socket: /tmp/nostalgiabox-phase25-mpv.sock
```

1. Check out the reviewed Task 2.5 branch on the Dell and install the backend development package.
   Do not alter `/opt/nostalgiabox/launch.sh`, autologin, X startup, boot configuration, the
   production database or `/run/nostalgiabox/mpv.sock`.
2. Migrate only the temporary proof database:

   ```bash
   NOSTALGIABOX_DATABASE_URL=sqlite:////tmp/nostalgiabox-phase25.db alembic upgrade head
   ```

3. Create `/tmp/nostalgiabox-phase25.json` outside Git. Use Channel 001, at least three logical
   entries of 20–30 seconds, a UTC start chosen so execution begins part-way through entry A, and
   operator-owned media paths. Multiple logical items may point at the same physical test video.
4. Seed only that explicit temporary target:

   ```bash
   nostalgiabox-seed \
     --database-url sqlite:////tmp/nostalgiabox-phase25.db \
     --manifest /tmp/nostalgiabox-phase25.json
   ```

5. In the `nostalgia` user's active X session, start one isolated proof MPV. Because the Phase 1 MPV
   owns HDMI audio, `--no-audio` is allowed and does not reopen Task 2.4 audio acceptance:

   ```bash
   DISPLAY=:0 mpv \
     --idle=yes --force-window=yes --keep-open=yes \
     --input-ipc-server=/tmp/nostalgiabox-phase25-mpv.sock \
     --fs --no-border --hwdec=vaapi --no-audio
   ```

6. Run continuous proof mode:

   ```bash
   nostalgiabox-channel-proof \
     --database-url sqlite:////tmp/nostalgiabox-phase25.db \
     --socket /tmp/nostalgiabox-phase25-mpv.sock \
     --channel-number 1 \
     --poll-seconds 0.5
   ```

7. Confirm the initial load selects entry A at the logged non-zero wall-clock offset. Leave it
   running through a short boundary and confirm exactly one load of entry B at its current near-zero
   offset. Stop only the proof runtime with Ctrl+C, wait several seconds, restart the same command,
   and confirm it recomputes the current entry/offset instead of resuming remembered player state.
8. Forced resync after simulated lost time/suspend is covered automatically with FakeClock. Task 2.5
   intentionally provides no system suspend hook or additional manual control endpoint.

Record timestamps, selected entry IDs, target offsets and visible playback results. Task 2.5 remains
PARTIAL on reference hardware until this session is completed.

## Unit-test requirements

### Time and timeline boundaries

For an entry `[start, end)`:

1. `now == start` resolves to the entry with offset zero.
2. `start < now < end` resolves to the entry with exact elapsed offset.
3. `now == end` does not resolve to the finished entry and should resolve to the next contiguous entry where present.
4. One microsecond/millisecond/second before a boundary resolves consistently according to the chosen timestamp precision.
5. A time before the available timeline returns an explicit not-covered result/error.
6. A time after the available timeline returns an explicit not-covered result/error.
7. Timeline gaps are detected.
8. Timeline overlaps are detected.
9. Zero/negative-duration entries are rejected.
10. A naive datetime is rejected rather than interpreted using machine-local timezone implicitly.

### Seek calculations

1. Offset at entry start is zero.
2. Mid-entry offset equals `now - start` exactly at domain precision.
3. Offset can never be negative for a correctly resolved entry.
4. Offset must remain below entry duration for a correctly resolved `[start, end)` entry.
5. Duration/offset conversion to MPV units is tested independently of the timeline calculation.

### Determinism

1. Same timeline + same fake clock gives the same active entry and offset across repeated runs.
2. Runtime restart does not alter the resolved channel state for a fixed clock.
3. Database read/write round trips do not change entry boundaries.

## Timezone and DST tests

The domain stores absolute UTC instants, but configured local schedule/display timezone behaviour must be tested using at least `Europe/London`.

Required cases:

- normal GMT date;
- normal BST date;
- spring-forward transition where a local hour is skipped;
- autumn fallback where a local hour is repeated;
- conversion of local authoring/display time to a unique absolute instant where possible;
- explicit handling/rejection of ambiguous local authoring times rather than silently choosing incorrectly.

The core active-entry algorithm should operate on UTC and therefore remain unambiguous once entries exist.

## Persistence tests

1. Clean database migration from zero succeeds.
2. Applying migrations repeatedly does not corrupt state.
3. Media/channel/timeline records round-trip correctly.
4. UTC-aware time semantics are preserved by repository conversion.
5. Duplicate channel-number constraints follow the approved schema.
6. Foreign-key/reference failures produce controlled errors.
7. Test database can be created without writing into production `/var/lib/nostalgiabox`.

## MPV adapter tests

### Automated/fake tests

- player command is issued with correct media path/reference;
- target seek offset is converted correctly;
- pause and resume commands are represented correctly;
- player unavailable/socket unavailable is handled explicitly;
- malformed/unexpected player response does not corrupt channel state;
- fake player records commands for application-level assertions.

### Reference-hardware integration tests

- connect to/control real MPV using JSON IPC;
- load H.264 test media using the proven hardware decode path;
- load representative HEVC/H.265 test media where available;
- seek near beginning/middle/end of a file;
- pause/resume;
- query playback state/time;
- kill MPV and demonstrate controlled detection/recovery behaviour;
- confirm audio/full-screen output remains correct on the Dell.

## One-channel proof test matrix

Create a deterministic Channel 001 timeline with multiple entries and known durations.

At minimum demonstrate:

| Scenario | Expected result |
| --- | --- |
| Tune exactly at Entry A start | Entry A starts at 00:00 |
| Tune part-way through Entry A | Entry A starts at exact elapsed offset |
| Tune one moment before A/B boundary | Entry A at near-end offset |
| Tune exactly at A/B boundary | Entry B starts at 00:00 |
| Tune part-way through Entry B | Entry B starts at exact elapsed offset |
| Restart runtime with fixed/current clock | Same live entry/offset is recomputed |
| Advance fake clock across boundary | Resolution moves to next entry |
| Real programme boundary during playback | Runtime transitions without returning to shell/menu |
| Suspend/wait/resume then live re-sync | Runtime recalculates current live position |

For real-hardware timing evidence, allow a small documented player-start/seek tolerance; the domain calculation itself must remain exact at its chosen precision.

## Failure tests

### Missing media

- timeline entry references a media item whose path is absent;
- core remains alive;
- failure is logged with channel/entry/media context;
- proof fallback/retry policy is explicit.

### Corrupt or unplayable media

- MPV rejects/aborts the item;
- core receives a controlled playback failure;
- no raw terminal/desktop UI is exposed;
- timeline state remains authoritative.

### Player process failure

- terminate MPV during playback;
- core detects the failure;
- core can restart/reconnect according to the chosen supervision model;
- after recovery, current wall-clock time is re-resolved before playback resumes.

### Database unavailable/corrupt for proof purposes

- startup error is controlled and clearly logged;
- core does not silently create a conflicting second production state unless explicitly configured to initialise a new DB.

## Input abstraction tests

1. Keyboard and reference remote produce logical actions through an adapter/profile boundary.
2. Raw `/dev/input/eventN` values are not persisted as stable identifiers.
3. Changing a profile mapping does not require editing timeline-domain code.
4. Unhandled mouse/air-mouse activity does not affect channel scheduling logic.
5. Reference remote wake-from-S3 limitation remains documented and is not treated as a Phase 2 software failure.

## API/health tests

If Phase 2 exposes proof endpoints:

- `/health` or equivalent returns service health without database secrets/paths that should remain private;
- current-state endpoint accurately reports resolved channel/entry/offset;
- API serialization does not introduce naive datetimes;
- API failure does not stop core playback/scheduling logic unnecessarily.

## Reference-appliance acceptance session

Before Phase 2 closes, run a documented session on the Dell OptiPlex 7050 that includes:

1. cold/restart into the Phase 2 runtime;
2. Channel 001 tune at a known mid-programme time;
3. confirm displayed/observed file and target seek offset;
4. wait through a programme boundary;
5. restart the core and confirm live rejoin;
6. suspend long enough for expected channel position to advance, wake and trigger re-sync;
7. terminate MPV and confirm documented recovery behaviour;
8. run at least one missing/unplayable-media case;
9. verify keyboard/reference remote input reaches the logical-action layer.

## Phase 2 exit review

Phase 2 may close only when:

- all architecture/technology ADRs match the implementation;
- the one-channel proof passes on reference hardware;
- automated boundary/time tests pass;
- player and persistence failure cases are controlled;
- no UI layer duplicates the authoritative real-time calculation;
- unresolved issues are explicitly assessed as non-blocking for Phase 3;
- documentation is updated with measured evidence and final service boundaries.
