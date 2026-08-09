# Phase 2 — Final Requirement Traceability

## Closure decision

**Final status: PASS / complete — 2026-08-09.** Every Phase 2 requirement is either satisfied
with implementation and evidence or explicitly deferred by the scope approved before implementation.
There are no `PARTIAL` or `FAIL` requirements. Deferred items below are product integrations that
Phase 2 expressly excludes; none is required to prove the one-channel architecture.

Evidence abbreviations:

- **T2.7 integration:** `backend/tests/integration/test_phase2_closure.py`
- **Architecture tests:** `backend/tests/unit/test_architecture.py`
- **Dell evidence:** the measured Task 2.1–2.6 sessions in `TESTING.md`

## Scope and real-time channel behaviour

| Requirement | Status | Implementation location | Automated evidence | Dell / documentation evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- |
| Core runtime/service boundaries defined | PASS | `application.runtime`, application ports, `persistence.runtime_sources`, attach-only playback/input adapters | Architecture tests; runtime unit/integration suites | `ARCHITECTURE.md`; ADR-006/007/009 | Permanent service units are later production integration, not a Phase 2 implementation requirement. |
| Backend language/framework selected | PASS | Python 3.13 package and FastAPI application factory | API/settings suites | Task 2.1 Debian install/API probe; ADR-007 | None. |
| Embedded database/migration approach selected | PASS | SQLite, SQLAlchemy 2, Alembic revision `20260808_0001` | Migration, repository and T2.7 integration tests | Task 2.1/2.3 Debian evidence; ADR-008 | None. |
| Playback-control boundary around MPV | PASS | `application.player`, `playback.mpv`, `playback.transport` | Playback unit/AF_UNIX integration tests | Task 2.4 real-MPV Dell proof; ADR-009 | None. |
| Minimum media/channel/timeline/runtime model | PASS | `domain.models`, `domain.timeline`, `persistence.media`, `RuntimeSnapshot`/`RuntimeFailure` | Domain, mapper, repository and runtime tests | `ARCHITECTURE.md` approved model reconciliation | Channel enabled state is explicitly later application/persistence work; see deferred table. |
| Deterministic real-time resolution | PASS | `ChannelTimeline`, `resolve_active_entry`, `ChannelRuntime` | Domain suite and T2.7 integration | Task 2.5 Dell Channel 001 proof | None. |
| Explicit UTC/timezone handling | PASS | `domain.time`, exact persistence codecs, aware settings/manifest boundaries | Domain DST tests and T2.7 migrated spring/fold tests | ADR-010 and `ARCHITECTURE.md` | Local schedule authoring is later scope. |
| Restart/rejoin behaviour | PASS | Fresh `ChannelRuntime.synchronise()` reads clock/timeline and never a playback cursor | Runtime unit suite and T2.7 integration | Task 2.5 Dell restart/rejoin | None. |
| Input abstraction suitable for USB remote | PASS | `InputAction`, `RemoteProfile`, `LinuxInputSource`, application controller | Input and architecture tests | Task 2.6 Nordic remote-to-real-MPV proof | Final navigation action set belongs to Phase 5. |
| Process-supervision expectations defined | PASS | Attach-only adapters; bounded reconnect; core/MPV separately supervised direction | Player-loss runtime tests | Task 2.6 isolated MPV loss/recovery; ADR-006/009 and `ARCHITECTURE.md` | Permanent systemd units are approved later production integration. |
| Channel 001 contains at least two known-duration items | PASS | External seed manifest and sequential timeline builder | Seed suite and T2.7 three-item manifest | Task 2.5 Dell timeline | None. |
| Timeline advances while unwatched | PASS | Resolution derives solely from injected current clock and absolute timeline | FakeClock boundary/restart tests; T2.7 integration | Task 2.5 wall-clock boundary evidence | None. |
| Active interval is `start_utc <= now < end_utc` | PASS | `resolve_active_entry` | Exact start, pre-boundary and boundary tests; T2.7 exact boundary | Task 2.5 boundary evidence | None. |
| Offset equals `now_utc - start_utc` | PASS | Domain resolver returns exact `timedelta` | Domain/runtime/T2.7 exact-offset assertions | Task 2.5 measured live offsets | None. |
| Player opens correct media at live offset | PASS | `ChannelRuntime._load()` through `Player.load()` | Runtime, persistence and T2.7 integration | Task 2.5 real MPV tune | None. |
| Runtime restart ignores stale player position | PASS | No player-position read in initial synchronisation | T2.7 explicitly seeks FakePlayer stale, creates a new runtime, and reloads current truth | Task 2.5 Dell fresh-process rejoin | None. |
| Resume can re-resolve rather than trust frozen playback | PASS | Explicit `ChannelRuntime.resynchronise()` reloads timeline and forces current live load | Same-entry/cross-boundary resync unit tests and T2.7 integration | Phase 1 suspend/resume; Task 2.6 same-entry/cross-boundary recovery | Automatic OS resume-event wiring is deferred by the approved architecture. |
| Valid deterministic boundaries have no gaps/overlaps | PASS | `ChannelTimeline` validation and sequential builder | Gap/overlap/order and exact-boundary tests | Task 2.5 visible boundary proof | None. |

## Time, playback, domain and persistence

| Requirement | Status | Implementation location | Automated evidence | Dell / documentation evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- |
| Absolute instants represented/persisted in UTC | PASS | UTC-normalized domain values and signed integer epoch-microsecond codecs | Codec/repository tests and T2.7 migrated DST tests | ADR-010 | None. |
| Local timezone is not an implicit storage format | PASS | `normalize_utc`; `Settings.local_timezone` remains presentation/configuration data | Naive rejection, non-UTC normalization and exact round trips | `ARCHITECTURE.md` | None. |
| Core works with timezone other than configured default | PASS | All aware datetime inputs normalize to UTC independently of machine timezone | UTC, Europe/London and settings override tests; T2.7 integration | ADR-010 | None. |
| Clock is injectable | PASS | `Clock`, `SystemClock`, test-only `FakeClock` | Deterministic repeated/advanced clock tests | Task 2.5/2.6 evidence | None. |
| DST/clock changes cannot duplicate absolute entries | PASS | UTC timeline identity and half-open intervals | Spring-forward/fold unit tests plus migrated/runtime T2.7 cases | ADR-010 | Local ambiguous-time authoring policy belongs to the later authoring feature. |
| MPV remains the playback engine | PASS | `MpvPlayer` adapter | Adapter tests | Phase 1 playback and Task 2.4/2.5/2.6 real-MPV evidence | None. |
| Application uses an adapter, not terminal parsing | PASS | `Player` protocol and structured JSON IPC transport/events | Playback/architecture tests | Task 2.4/2.6 Dell evidence; ADR-009 | None. |
| JSON IPC over Unix socket is the selected control channel | PASS | `MpvJsonIpcTransport` | AF_UNIX integration test | Real Unix-socket Dell proofs | None. |
| Player supports load, seek, pause/resume, stop, position, state and health | PASS | `Player`, `MpvPlayer`, `FakePlayer` | Player/MPV suites | Task 2.4 Dell control session | None. |
| Scheduling is testable without MPV | PASS | Injected `Player`; `FakePlayer` | Runtime and T2.7 integration suites | Documented architecture | None. |
| Hardware decode remains available | PASS | Deployment-owned MPV flags outside business logic | Not simulated | Phase 1 VA-API and Task 2.4–2.6 fullscreen VA-API proofs | None. |
| Media stable identity/title/duration and path boundary | PASS | Pure `MediaItem`; `StoredMediaItem` owns path | Model/mapper/repository tests | Approved Task 2.2/2.3 architecture | None. |
| Channel identity/number/name | PASS | Pure `Channel` and persistence record | Model/repository/seed tests | Channel 001 Dell proof | None. |
| Timeline entry owns content kind and UTC interval | PASS | `TimelineEntry`, `ContentKind` | Domain/persistence tests | `ARCHITECTURE.md` | None. |
| Runtime state represents selected channel/entry/player outcome | PASS | `RuntimeSnapshot`, `RuntimeFailure`, Player state/controller | Runtime/API tests | Task 2.5/2.6 observation evidence | None. |
| Timeline supports future non-programme kinds without redesign | PASS | `ContentKind` lives on timeline entries | Validation/mapping tests | ADR-004 and `ARCHITECTURE.md` | Only `PROGRAMME` is intentionally implemented now. |
| SQLite owns appliance persistence | PASS | Backend engine/session/repositories | Database/repository tests | ADR-008 | None. |
| Frontends do not own schema access | PASS | Persistence package and observation-only API | Architecture/API tests | ADR-008/011 | None. |
| Schema changes use migrations | PASS | Alembic baseline revision | Full lifecycle test and closure command run | Task 2.3 evidence | None. |
| Production DB stays outside Git | PASS | Production validation requires explicit persistent URL | Settings tests and artifact audit | Intended `/var/lib/nostalgiabox` path documented | None. |
| Tests use isolated databases | PASS | In-memory and `tmp_path` file-backed databases | Complete persistence/integration suite | No production DB touched | None. |

## Input, API and non-functional requirements

| Requirement | Status | Implementation location | Automated evidence | Dell / documentation evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- |
| Raw Linux event codes do not leak into channel/playback logic | PASS | Key value exists only in `input.profile`; evdev details terminate in `input.linux` | Input and architecture source tests | Task 2.6 mapping proof | None. |
| Physical events translate to logical actions | PASS | `LinuxInputSource` → `RemoteProfile` → `InputAction` | Press/release/repeat/remap tests | Task 2.6 remote proof | None. |
| Only minimum input proof is implemented | PASS | `PLAY_PAUSE` only | Controller tests | Remote-to-real-MPV pause/resume | Later navigation is deliberately not prebuilt. |
| Nordic wake limitation is non-blocking and documented | PASS | No power interception in Task 2.6 | Scope/architecture checks | Phase 1 remote evidence | Replacement receiver remains a later accessory decision. |
| Stable future API boundary exists | PASS | FastAPI factory, `/health`, read-only `/runtime` | API suite and architecture tests | Task 2.1 live health evidence | Phase 3 adds product endpoints rather than bypassing application ports. |
| Phase 2 does not build administration WebUI | DEFERRED-BY-APPROVED-SCOPE | No frontend implementation | Repository audit | ADR-011; explicit requirements deferral | Phase 3 responsibility. |
| Phase 2 does not select a heavyweight TV framework | DEFERRED-BY-APPROVED-SCOPE | MPV-only proof presentation | Dependency audit | ADR-011 | Phase 5/7 framework decision. |
| Full guide/Enhanced Guide Mode excluded | DEFERRED-BY-APPROVED-SCOPE | No guide implementation | Repository audit | Requirements and ADR-005/011 | Phase 7/8 responsibility. |
| Scheduling is deterministic/unit-testable | PASS | Pure domain plus injected ports | Domain/runtime/T2.7 suites | Dell proof | None. |
| Core tests need no TV/X/MPV | PASS | FakeClock/FakePlayer and temporary SQLite | Full automated suite | Test policy documented | None. |
| Invalid/missing media is controlled | PASS | `PlayerMediaLoadError`, `RuntimeFailure`, retry suppression | Runtime/playback/T2.7 tests | Task 2.6 missing/corrupt Dell proofs | None. |
| Structured diagnostics identify playback context | PASS | JSON formatter and runtime/input structured fields | Logging/API tests | Task 2.5/2.6 recorded outputs | None. |
| Core remains local-first | PASS | Runtime, DB, MPV and input require no cloud service | Dependency/repository audit | All Dell proofs ran locally | None. |
| Production services use non-root identity where practical | DEFERRED-BY-APPROVED-SCOPE | Service ownership direction documented; adapters require no root | Architecture tests | Phase 1 `nostalgia` appliance session; ADR-006 | Permanent production units/permissions are later service integration. |

## Explicit Phase 2 exclusions

| Requirement/exclusion | Status | Evidence and owner |
| --- | --- | --- |
| Full media scanning and matching | DEFERRED-BY-APPROVED-SCOPE | No scanner exists; Phase 3 catalogue work. |
| SMB/NAS source management | DEFERRED-BY-APPROVED-SCOPE | No network-source lifecycle exists; Phase 3. |
| Production administration WebUI | DEFERRED-BY-APPROVED-SCOPE | ADR-011 selects the later client direction; Phase 3 implements it. |
| Multiple editable channels | DEFERRED-BY-APPROVED-SCOPE | Phase 2 proves seeded Channel 001; Phase 4 owns editable multi-channel behaviour. |
| Advanced scheduling rules | DEFERRED-BY-APPROVED-SCOPE | Phase 4/9. |
| Channel logos/artwork | DEFERRED-BY-APPROVED-SCOPE | Phase 3/5 presentation/catalogue work. |
| Full TV menu or guide | DEFERRED-BY-APPROVED-SCOPE | Phase 5/7/8. |
| Adverts/promotions/advanced continuity | DEFERRED-BY-APPROVED-SCOPE | ADR-004; Phase 9/11. |
| Plex/Jellyfin integration | DEFERRED-BY-APPROVED-SCOPE | Later source adapters after the local catalogue. |
| Final remote selection | DEFERRED-BY-APPROVED-SCOPE | Current remote proves input; wake-capable replacement remains an accessory decision. |

## Exit-criteria assessment

| Exit criterion | Result | Evidence |
| --- | --- | --- |
| Accepted technology decisions | PASS | ADR-007 through ADR-011 match the implementation; ADR-003/006 provide behavioural/deployment direction. |
| Architecture boundaries documented | PASS | `ARCHITECTURE.md` plus executable architecture tests. |
| One Channel 001 resolves deterministically | PASS | Domain/runtime/T2.7 suites and Task 2.5 Dell proof. |
| Correct file and wall-clock offset | PASS | T2.7 full-path assertions and real MPV Dell evidence. |
| Restart/rejoin demonstrated | PASS | T2.7 stale-player test and Task 2.5 Dell restart. |
| Boundary, missing-file, timezone and player-failure tests recorded | PASS | Automated suites and Task 2.5/2.6 Dell evidence. |
| Suitable Phase 3 foundation without core rewrite | PASS | Stable domain/persistence/player/input/API boundaries and handoff below. |

## Suspend/resynchronisation conclusion

Phase 2 requirement 7 says resume **must allow** the runtime to re-resolve live truth. It does not
require Phase 2 to subscribe to an operating-system event. `ChannelRuntime.resynchronise()` provides
that explicit operation and is covered within/across entries through temporary migrated SQLite,
FakeClock/FakePlayer and Task 2.6 real-MPV recovery evidence. `ARCHITECTURE.md` explicitly assigns
automatic systemd sleep-hook integration to the future production runtime service. That wiring is
therefore `DEFERRED-BY-APPROVED-SCOPE`, while the Phase 2 resynchronisation requirement is `PASS`.

## Timezone/DST conclusion

Authoritative instants are aware UTC domain values persisted as exact epoch microseconds. Existing
unit tests distinguish both `Europe/London` autumn folds and cross the spring skip. Task 2.7 extends
this through migrated SQLite, repository reconstruction, `ChannelRuntime`, FakeClock and FakePlayer,
including aware non-UTC normalization. Local schedule authoring and ambiguous-input UX do not exist
in Phase 2 and remain later authoring concerns. The Phase 2 UTC/DST requirement is `PASS`.

## Phase 3 handoff

Phase 3 may rely on these foundations without redesign:

- Python 3.13/FastAPI backend and typed settings;
- SQLite/SQLAlchemy/Alembic with explicit transaction and migration ownership;
- pure domain values separated from ORM records and stored media paths;
- stable media identity plus the `StoredMediaItem` path boundary;
- deterministic contiguous timeline model and UTC policy;
- `Player` protocol, FakePlayer and attach-only MPV JSON IPC adapter;
- short-session runtime persistence adapters and read-only runtime observation boundary;
- logical input/profile abstraction;
- structured logging and controlled failure taxonomy.

Phase 3 must not assume any of the following exists:

- automatic media scanning/path validation or ffprobe metadata extraction;
- media-source lifecycle, removable-storage handling, SMB/NAS credentials or availability policy;
- catalogue matching, corrections, artwork or rich programme metadata;
- production administration authentication/authorization or product API endpoints;
- editable multi-channel scheduling, final fallback/skip policy or schedule repair;
- final TV UI, overlay, channel-navigation UX or automatic suspend-event wiring;
- permanent production systemd units, installer, updater, backup or restore.

These are handoff constraints, not Phase 2 defects.
