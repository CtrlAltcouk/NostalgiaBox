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
| Python backend skeleton | PASS | Task 2.1: Python 3.13 package installs; API, configuration, logging and layer scaffolding validated by pytest, Ruff and mypy. |
| SQLite/Alembic migration path | PARTIAL | Task 2.1: SQLAlchemy engine/session and empty Alembic environment validated. Domain tables and the first revision remain correctly deferred to Task 2.2/2.3. |
| Pure timeline domain engine | BLOCKED | Not yet implemented. |
| Fake clock / deterministic time tests | BLOCKED | Not yet implemented. |
| MPV JSON IPC adapter | BLOCKED | Not yet implemented. |
| Fake player adapter | BLOCKED | Not yet implemented. |
| Channel 001 seed timeline | BLOCKED | Not yet implemented. |
| Correct mid-programme tune offset | BLOCKED | Not yet implemented. |
| Restart/rejoin behaviour | BLOCKED | Not yet implemented. |
| Suspend/live re-sync path | BLOCKED | Not yet implemented. |
| Input abstraction proof | BLOCKED | Not yet implemented. |
| Missing/corrupt media handling | BLOCKED | Not yet implemented. |
| Player failure handling | BLOCKED | Not yet implemented. |
| Timezone/DST tests | BLOCKED | Not yet implemented. |

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
