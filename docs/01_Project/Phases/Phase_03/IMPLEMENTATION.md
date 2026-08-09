# Phase 3 — Basic Media Catalogue and Administration Web UI: Implementation Plan

## Status and delivery rules

**Implementation in progress — 2026-08-09.** Task 3.1 is implemented on its review branch and its
development validation passes; isolated reference-Dell validation remains pending. Later tasks and
Phase 3 as a whole are not implemented or accepted. Each task requires its own branch, review,
tests, migration lifecycle where applicable, documentation and proportionate reference-Dell
evidence. Phase 2 tests and architecture remain mandatory regression coverage.

Rules for every task:

- implement only the listed capability; do not pull Phase 4 channels or Phase 5 TV UI forward;
- domain/application code remains free of FastAPI, SQLAlchemy, ffprobe JSON, mount commands and
  React concerns;
- do not edit the Phase 2 migration; add reversible Alembic revisions;
- use temporary media/filesystems and fake ports in automation;
- never commit media, DB/WAL files, credentials, tokens, caches or generated frontend output;
- update requirement/test traceability in the same review.

## Task sequence

### Task 3.1 — Catalogue domain, ports and schema foundation

- **Objective:** Establish only the additive catalogue identity and playable-rendition foundation
  (`P3-CAT`, schema portions of `P3-CON`) without beginning discovery or product behavior.
- **Components:** pure catalogue/source/file/rendition/segment values and invariants; application
  repository and playable-projection ports; additive SQLAlchemy records/repositories; one new
  Alembic revision; compatibility adapter preserving existing `MediaItem`/`StoredMediaItem` reads.
- **Migration:** create `catalogue_items`, source/file and rendition/segment foundation tables;
  backfill every existing `media_items.id` into `catalogue_items` with the same ID. Do not alter or
  repurpose `media_items(id,title,duration_us,path)` or its timeline FKs. Downgrade drops only the
  additive Task 3.1 tables and leaves the Phase 2 schema/data intact.
- **Automated tests:** pure identity/segment invariants; whole-file and bounded segment projection;
  unplayable catalogue item; same-ID backfill; additive empty/Phase-2 upgrade/current/repeat/
  downgrade/re-upgrade; mapper/repository/FK behavior; compatibility projection and full Phase 2
  runtime regression; architecture/dependency rules.
- **Dell validation:** migrate a disposable copy/temporary DB under Python 3.13; never production DB.
- **Risks:** accidentally treating legacy `path` as identity, changing duration/path semantics, or
  coupling segment resolution into timeline/player/UI layers.
- **Exit:** additive identities/renditions exist, all Phase 2 IDs/runtime behavior remain intact,
  and no scanning, ffprobe, fingerprinting, SMB mount, matching parser, WebUI, authentication or
  Phase 4 timeline-generation behavior has been introduced.

#### Task 3.1 implementation evidence

- **Development status:** `PARTIAL` pending reference-Dell validation. The Windows/Python 3.13
  suite passes with 243 passed and the Linux-only AF_UNIX test skipped as expected.
- **Pure model:** immutable opaque IDs and minimum `CatalogueItem`, `MediaSource`, `MediaFile` and
  `PlayableRendition` values enforce source-relative locators and exact `timedelta` segment rules.
  One physical file may back adjacent non-overlapping renditions for several catalogue items.
- **Ports/projection:** caller-transaction-owned repository ports and a pure playback projection
  expose catalogue ID, resolved physical path, physical origin/end and logical duration. Timeline,
  React and API layers do not calculate segment positions.
- **Persistence:** revision `20260809_0002` adds only `catalogue_items`, `media_sources`,
  `media_files` and `playable_renditions`, with foreign keys, single-row checks, lookup indexes,
  per-source locator uniqueness and a partial unique index allowing at most one preferred rendition
  per catalogue item. Inter-row overlap is validated by the domain/repository because a SQLite
  `CHECK` constraint cannot inspect other rows.
- **Compatibility:** migration backfill copies each legacy `media_items.id` unchanged into
  `catalogue_items.id`; it does not alter legacy rows, paths, duration, timeline FKs or boundaries.
  The separate legacy projection resolver reads the existing same-ID `StoredMediaItem` path and
  duration. Catalogue-only items explicitly resolve as unplayable rather than manufacturing data.
  Production `ChannelRuntime` remains unchanged.
- **Migration proof:** automated empty and populated Phase 2 upgrade/repeat/downgrade/re-upgrade
  tests compare exact legacy row snapshots, exercise the Phase 2 runtime after upgrade, verify
  controlled foreign keys and prove a rejected invalid legacy ID creates no catalogue tables.
- **Scope:** no scanning, filesystem traversal, ffprobe, fingerprint, source lifecycle, API, WebUI,
  authentication, WAL, worker or scheduling behavior was added. ADR-012 and ADR-013 remain
  `Proposed`.

### Task 3.2 — Local source lifecycle and availability

- **Objective:** Add local-folder create/edit/test/enable/disable/retire application services
  (`P3-SRC-01`–`05`) without scanning.
- **Components:** source commands/queries and policies; local `SourceGateway`; source repository;
  sanitized failure mapping. No API routes yet beyond task-local tests unless separately approved.
- **Migration:** only narrowly necessary source status/index refinements after 3.1.
- **Automated tests:** approved-root canonicalization, traversal and symlink escape, protected-root
  rejection, explicit expert roots, readable/missing/permission roots, state transitions, disable/
  retire semantics, no secret/path leakage and transaction conflicts.
- **Dell validation:** isolated temporary internal folder owned by the test operator.
- **Risks:** symlink escape, case sensitivity and path disclosure.
- **Exit:** local sources have stable identity and controlled availability with no file discovery.

### Task 3.3 — Scan coordinator and deterministic local discovery

- **Objective:** Implement full/incremental traversal, durable runs, bounded batches, cancellation
  and interrupted-run recovery without ffprobe (`P3-SCAN`).
- **Components:** `ScanCoordinator`, worker/executor port, local traversal adapter, scan/file
  repositories, progress snapshot and issue taxonomy.
- **Migration:** scan-run/issue and observation-generation tables/indexes if not created in 3.1.
- **Automated tests:** initial/unchanged/add/change/remove, hidden/ignored/symlink cases, interrupted
  enumeration, cancellation, source loss, one-scan-per-source, idempotent replay and no premature
  missing reconciliation.
- **Dell validation:** scan generated small fixture trees while Phase 2 runtime reads a temporary DB.
- **Risks:** long transactions, event-loop blocking and excessive progress writes.
- **Exit:** source inventory is restart-safe and deterministic; no probe/matching exists yet.

### Task 3.4 — ffprobe metadata and supported-format policy

- **Objective:** Add structured technical inspection and transparent format states (`P3-PROBE`).
- **Components:** `MediaProbe` port, typed metadata/stream values, `FfprobeAdapter`, capability/version
  check, probe scheduling integration, metadata repositories.
- **Migration:** technical metadata/streams, probe signature/version and state columns.
- **Automated tests:** fake process runner JSON fixtures; exact duration/rational parsing; audio/
  subtitle streams; timeout, missing binary, exit failure, malformed/oversized JSON, corrupt and
  unsupported states; unchanged-file no-reprobe.
- **Dell validation:** explicit ffprobe version plus small operator-owned known-good/corrupt fixtures;
  no library-wide scan.
- **Risks:** hostile metadata/output size, subprocess leaks and incorrect “playable” claims.
- **Exit:** measured facts and failures persist through the typed boundary; no rich metadata matching.

### Task 3.5 — Rename, replacement and duplicate reconciliation

- **Objective:** Implement the tiered observation/fingerprint identity policy (`P3-CAT-03`–`08`).
- **Components:** quick/full fingerprint port and adapter, reconciliation policy, duplicate candidate
  and confirmation services, issue projections.
- **Migration:** fingerprint and duplicate-candidate/group records/indexes.
- **Automated tests:** same-path unchanged/change/replacement; local inode hint; unique rename;
  ambiguous move; partial-hash collision simulation; cross-source duplicate; optional full-hash
  confirmation; zero user-file mutations.
- **Dell validation:** temporary generated files across rename/copy/replace operations; benchmark
  sample size and hashing cost.
- **Risks:** false identity merges are worse than duplicates; ambiguity must stop auto-merge.
- **Exit:** stable IDs survive confident moves and collisions remain reviewable.

### Task 3.6 — Managed SMB/NAS source support

- **Objective:** Implement the approved direction of proposed ADR-012, finalize its review details,
  and deliver source lifecycle through the narrow mount/credential boundary (`P3-SRC`, SMB portions
  of `P3-SEC`).
- **Components:** SMB source configuration/application service; mount and secret-store protocols;
  privileged helper/systemd integration as separately reviewed infrastructure; CIFS availability
  adapter. Scanner still consumes an ordinary mounted path.
- **Migration:** source-type-specific non-secret configuration and opaque credential reference only.
- **Automated tests:** fake mount/secret adapters; create/test/replace credential/disable/retire;
  auth/permission/network errors; reconnect without mass deletion; no password serialization/logs.
- **Dell/NAS validation:** isolated test share and least-privilege account; boot/network loss,
  disconnect/reconnect, read/scan/probe/MPV path access; remove all temporary credentials/mounts.
- **Risks:** privileged command injection, mount ownership, reconnect semantics and secret exposure.
- **Exit:** local and SMB sources share catalogue behavior; secrets never enter ordinary DB/API/logs.

### Task 3.7 — Basic matching, durable corrections and artwork boundary

- **Objective:** Add unknown/movie/series/season/episode candidates, accepted matches, overrides and
  optional non-blocking artwork references (`P3-MATCH`, `P3-ART`).
- **Components:** pure filename candidate parser; matcher application service; hierarchy and match/
  override repositories; effective metadata projection with optimistic revision; artwork-reference
  records and rebuildable cache/placeholder boundary without cloud providers.
- **Migration:** series/seasons/details, match links and catalogue overrides if not already present.
- **Automated tests:** common/ambiguous filename patterns, fallback titles, multiple renditions,
  validated manual multi-episode segment assignment without duplicating `MediaFile`, precedence/
  clear behavior, correction across rescan/reprobe/rename/offline source, concurrent edit conflict,
  and missing/failed artwork never blocking catalogue or playback resolution.
- **Dell validation:** none beyond full regression; use synthetic filenames.
- **Risks:** false confident matches and mixing technical/editorial data.
- **Exit:** corrections persist and derived data can refresh without overwriting users.

### Task 3.8 — Versioned catalogue/source/scan API

- **Objective:** Expose the Phase 3 application services through stable `/api/v1` contracts
  (`P3-API`), initially with test authentication injection where necessary.
- **Components:** Pydantic request/response models, thin routers/dependencies, pagination, ETag/
  revision handling, safe error envelope and OpenAPI contract artifact/check.
- **Migration:** none expected.
- **Automated tests:** validation/status codes, pagination/filtering, 202 scan operations, conflicts,
  error redaction, no ORM/filesystem/probe imports in routes, unchanged `/health` and `/runtime`.
- **Dell validation:** live local API probes against disposable catalogue data.
- **Risks:** leaking roots/issues and binding routes directly to repositories.
- **Exit:** complete non-secret administration contract exists without frontend/business duplication.

### Task 3.9 — React/Vite administration foundation and authentication screens

- **Objective:** Create the ADR-011 client shell, typed API boundary, routing, responsive design and
  setup/login/dashboard/system states (`P3-UI`).
- **Components:** `frontend/admin`, Vite/TypeScript/React config, API client generation/check, router,
  query cache, accessible component shell, browser-test harness. No TV UI.
- **Migration:** none.
- **Automated tests:** type/lint/unit/component checks, contract drift, error/loading/empty states,
  accessibility smoke, desktop/phone browser navigation with fake API.
- **Dell validation:** serve built assets through intended local path and inspect from desktop/phone;
  no kiosk/TV benchmark implied.
- **Risks:** premature design system, business logic in components and generated artifacts in Git.
- **Exit:** responsive authenticated shell consumes typed mock/live API without catalogue screens yet.

### Task 3.10 — Source, scan, library and correction WebUI

- **Objective:** Deliver the Phase 3 administration workflows (`P3-UI-02`–`06`).
- **Components:** source forms/test/retire, scan progress/history/issues polling, library filters/
  pagination, attention queue, detail/correction forms and system/storage panels.
- **Migration:** none expected.
- **Automated tests:** user flows with mocked API and integrated temporary backend; stale/conflict,
  retry/offline/partial failure, keyboard/accessibility, responsive desktop/phone viewports.
- **Dell validation:** complete local and test-NAS setup/scan/correction from real desktop and phone
  browsers without terminal access.
- **Risks:** exposing credentials in form state/history and polling overload.
- **Exit:** routine catalogue setup and correction require no Linux interaction.

### Task 3.11 — Authentication, secrets and concurrency hardening

- **Objective:** Implement the approved direction of proposed ADR-013, finalize its setup-token/
  secret-helper review, enable validated SQLite concurrency policy and exercise combined workloads
  (`P3-SEC`, `P3-CON`).
- **Components:** admin/session services, password hashing, CSRF/Origin/Host/rate-limit middleware,
  secret-store/helper boundary, redaction, scan worker recovery, WAL/busy configuration.
- **Migration:** admin users/sessions/audit data; no reversible secret material in DB.
- **Automated tests:** claim/login/logout/revoke/expiry/rate limit/CSRF/host checks, secret permissions
  via fake adapter, redaction, restart/interrupted jobs, busy retry bounds, scan+runtime+API reads.
- **Dell validation:** first-run claim through approved physical/local method; browser session from
  desktop/phone; permissions audit; concurrent playback, scan and catalogue browsing; reboot.
- **Risks:** bootstrap takeover, LAN plaintext confidentiality, WAL/backup interaction, starvation.
- **Exit:** authenticated local administration and secrets/concurrency behavior meet threat model.

### Task 3.12 — Phase 3 integration, reference validation and closure

- **Objective:** Audit every Phase 3 requirement and prove the complete local/NAS catalogue-to-WebUI
  path without adding features.
- **Components:** final cross-layer tests, traceability/evidence docs, supported-format measurements,
  architecture/dependency/artifact audit and roadmap closure only if honestly satisfied.
- **Migration:** prove empty upgrade, upgrade from Phase 2 data, current/repeat/downgrade/re-upgrade
  and failure recovery on temporary DBs.
- **Automated tests:** full backend/frontend suites and the matrix in `TESTING.md`.
- **Dell/NAS validation:** isolated end-to-end local and SMB scans, ffprobe, rename/offline/reconnect,
  correction persistence, concurrent playback, desktop/phone administration and security checks.
- **Risks:** treating prior task existence as acceptance or hiding a real gap as deferred.
- **Exit:** explicit traceability has no unapproved partial/fail; Phase 3 is PASS or precisely blocked.

## Dependency order

```text
3.1 -> 3.2 -> 3.3 -> 3.4 -> 3.5
                  \             \
                   \-> 3.6       -> 3.7 -> 3.8 -> 3.10
                                      \-> 3.9 ---/
3.6 + 3.8 + 3.9 + 3.10 -> 3.11 -> 3.12
```

3.9 can begin after API contracts stabilize in 3.8 (or against checked fixtures during late 3.8),
but source/library workflows must not invent contracts independently.

## Traceability summary

| Requirement group | Owning tasks |
| --- | --- |
| `P3-CAT` | 3.1, 3.5, 3.7, 3.12 |
| `P3-SRC` | 3.2, 3.6, 3.8, 3.10, 3.12 |
| `P3-SCAN` | 3.3, 3.4, 3.5, 3.6, 3.8, 3.10–3.12 |
| `P3-PROBE` | 3.4, 3.12 |
| `P3-MATCH` | 3.7, 3.8, 3.10, 3.12 |
| `P3-ART` | 3.7, 3.12 |
| `P3-API` | 3.8, 3.11, 3.12 |
| `P3-UI` | 3.9, 3.10, 3.12 |
| `P3-SEC` | 3.6, 3.9–3.12 |
| `P3-CON` | 3.1, 3.3, 3.11, 3.12 |
