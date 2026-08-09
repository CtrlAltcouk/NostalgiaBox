# Phase 3 — Basic Media Catalogue and Administration Web UI: Architecture

## Status and governing decisions

**Proposed for architectural review — 2026-08-09.** No production component described here has
been implemented. This design extends ADR-007 through ADR-011 and the accepted Phase 2 boundaries.
Proposed [ADR-012](../../../ADR/ADR-012-managed-cifs-media-sources.md) covers SMB ownership;
proposed [ADR-013](../../../ADR/ADR-013-local-administration-security-and-secrets.md) covers
administration authentication and secret storage.

## System boundaries

```text
React administration client
          |
     /api/v1 DTOs
          v
FastAPI routes -> catalogue/source/scan/auth application services -> domain policies
                         |              |              |
                  repository ports  source ports   probe/secret ports
                         |              |              |
                    SQLAlchemy     local/CIFS FS   ffprobe/secret files

Phase 2 timeline/runtime -> catalogue playback-location resolver -> Player -> MPV
```

Routes validate transport concerns and call services. Services own use-case transactions and
policy. Infrastructure implements SQLAlchemy, filesystem/CIFS, subprocess and secret boundaries.
Neither scanning nor WebUI code enters the timeline or MPV packages.

## Catalogue model

### Logical versus physical

| Concept | Identity and responsibility |
| --- | --- |
| `MediaSource` | Generated immutable ID for one configured local root or managed SMB share; configuration and availability only. |
| `MediaFile` | Generated immutable ID for an observed physical file; source-relative locator, observation signature, lifecycle and probe state. |
| `CatalogueItem` | Broader stable logical programme identity. Existing Phase 2 IDs are backfilled unchanged; new items may exist without a playable projection. |
| `PlayableRendition` | File-to-catalogue association selecting a whole file or bounded segment, preferred state and explicit logical playable duration. |
| `Series` / `Season` | Logical hierarchy; seasons belong to series and episodes link to a season. |
| `Movie` / `Episode` | Typed detail attached to a catalogue item rather than separate playback identity. |
| `TechnicalMetadata` | Versioned measured facts for one file; never editorial truth. |
| `MediaMatch` | Provenanced matching decision/candidate, separate from the playable rendition and its segment bounds. |
| `ScanRun` / `ScanIssue` | Durable execution/progress and sanitized per-source/per-file problems. |
| `CatalogueOverride` | Explicit field-level editorial values; stored separately from derived values. |
| `ArtworkReference` | Optional logical reference and rebuildable cache key; never an identity/playback dependency. |

Several encodes/locations may back one programme. A confirmed multi-episode file remains one
`MediaFile` with multiple segment renditions rather than duplicated physical records. Most
renditions cover one whole file. A resolver selects one available, compatible preferred rendition
and returns a Phase 2-compatible playable projection. Playback never receives a path selected by
React.

### Additive Phase 2 compatibility boundary

Task 3.1 does **not** repurpose or replace `media_items(id, title, duration_us, path)`. It adds a
separate `catalogue_items` table and backfills every existing Phase 2 media ID into it using the
same ID. Existing `timeline_entries.media_item_id` foreign keys remain untouched, and the existing
runtime/repositories continue to read `media_items` and `StoredMediaItem` throughout staged Phase 3
delivery.

`media_items` is initially the playable compatibility projection of a catalogue item. New
catalogue items may exist before any file is playable. Once a whole-file or segmented rendition is
explicitly selected and validated, a compatible `MediaItem` projection uses that same stable ID,
an explicit logical title/duration and a resolved path. The legacy `media_items.path` remains a
documented fallback during rollout; no catalogue/scanner identity is derived from it.

The first migration is additive and lossless: create new tables, backfill catalogue identities and
leave Phase 2 rows/constraints/FKs intact. Its downgrade removes only the new Phase 3 foundation and
does not require inspecting or rewriting Phase 2 paths. Later catalogue data needs ordinary backup
guidance, but Task 3.1 has no data-dependent compatibility downgrade.

The legacy path column may be retired only in a later reviewed migration after all playable rows
have catalogue renditions, every runtime/playback lookup uses the resolver, Phase 2 compatibility
and rollback windows are explicitly closed, timeline IDs remain stable, migration/reference tests
pass, and no supported deployment still depends on the fallback.

### Playable segment model

A rendition stores `media_file_id`, `catalogue_item_id`, whether it covers the whole file,
`segment_start_us`, `segment_duration_us` (with derived `segment_end_us`), preferred/availability
state and the explicit logical playable duration. Invariants are:

```text
segment_start_us >= 0
segment_duration_us > 0
segment_end_us = segment_start_us + segment_duration_us
segment_end_us <= measured physical duration when that fact is available
logical playable duration > 0 and fits inside the segment
```

A normal movie/episode starts at zero and uses the complete validated physical/effective duration.
For `S01E01-E02`, separate catalogue IDs reference non-overlapping ranges of the same `MediaFile`.
Automatic split-point inference is not required in Phase 3; initial segment assignment may be a
validated manual correction. Overlap between independently playable episode segments is rejected
unless a future explicitly reviewed use case defines why it is valid.

The playback-location resolver returns a value equivalent to:

```text
physical_path
physical_start_offset = segment_start_us
logical_playable_duration
segment_end
```

The runtime converts a logical live offset to physical MPV position by adding the segment origin
inside the application playback-resolution boundary. React and the timeline domain do not perform
this calculation.

### Duration and schedule-truth policy

`TechnicalMetadata.duration` is a measured fact about one `MediaFile`. It never automatically
updates `media_items.duration_us` or existing `TimelineEntry` boundaries. Changing preferred
rendition/location likewise cannot rewrite historical/current schedule truth.

Creating or replacing a playable projection explicitly validates logical duration against the
selected whole-file/segment range. Incompatible multi-rendition durations, shortened files and
segment discrepancies become Needs Attention issues until resolved. Catalogue matching, rendition
selection and timeline publication are separate operations. Phase 4 owns the policy for using
catalogue durations to generate future timeline entries; already-published absolute intervals stay
immutable under Phase 2 rules.

## Stable identity policy

IDs are random UUIDs/ULIDs generated once and never derived from path or title.

### Observation signals

1. `(source_id, normalized_relative_path)` plus size and nanosecond modification time identifies an
   unchanged observation cheaply.
2. Local device/inode may support same-source rename detection only when accompanied by size/time
   checks; it is a hint, never portable identity.
3. A bounded quick fingerprint (size plus sampled content digest) is computed for new, changed,
   moved or duplicate-candidate files, not every unchanged scan.
4. A full content hash is optional/on-demand for ambiguous collisions, administrator confirmation
   or exact duplicate verification.

The relative path uses normalized Unicode and separators, rejects traversal and is unique within a
source under the source's documented case-sensitivity policy. Original spelling is retained for
display/access.

### Rename, replacement and collision behavior

- Exact unchanged observation keeps `MediaFile.id`.
- A missing old path and new path with one unambiguous inode or quick-fingerprint match updates the
  locator and preserves ID, matches and corrections.
- Multiple candidates, weak/colliding fingerprints or cross-source similarity create new file IDs
  and `file.possible_duplicate` issues. They are never auto-merged.
- Materially different content at the same path retires the prior file observation and creates a
  new file ID. A locked manual logical mapping may be proposed for reuse but is not silently copied
  when the evidence conflicts.
- Confirmed duplicates remain separate locations with a duplicate-group/fingerprint relation. The
  system never deletes or hard-links user data.
- Editorial corrections belong to stable catalogue IDs/match locks, so path movement and reprobe do
  not overwrite them.

## Source lifecycle and SMB/NAS

Enabled state, availability and scan state are independent:

```text
enabled: true/false
availability: unknown | available | unavailable | authentication_failed |
              permission_denied | invalid_root | error
scan run: queued | running | completed | cancelled | interrupted | failed
```

A failed availability check updates source diagnostics but does not run missing-file reconciliation.
Removing a source retires it and its file locators. Logical items and overrides remain. A later
explicit purge must be blocked while timeline or other protected references exist.

### Local source allowed roots

Normal WebUI source creation selects folders only beneath deployment-approved media roots. The
default appliance root is `/srv/nostalgiabox/media`; the configuration is an allow-list so future
storage volumes can be added deliberately without permitting arbitrary browsing.

Before storing or scanning, the local adapter joins the approved root and requested relative path,
resolves the canonical/real path, and verifies it remains beneath the canonical approved root.
Reject absolute/traversal input, symlink escapes and roots resolving into `/etc`, `/home`,
`/var/lib/nostalgiabox`, secret/cache/runtime state or other protected system trees. Apply the same
check during traversal to prevent a symlink introduced after configuration from escaping.

Externally pre-mounted paths outside normal managed roots require explicit expert deployment
allow-list configuration and are never enabled merely by typing an arbitrary WebUI path. Managed
SMB paths remain confined to `/run/nostalgiabox/media/<source-id>` and are validated against the
configured source ID.

### SMB recommendation

Use OS-mounted CIFS shares managed through a narrow NostalgiaBox mount boundary. The scanner and MPV
see stable ordinary paths such as `/run/nostalgiabox/media/<source-id>`. A privileged helper or
templated systemd mount unit (implemented only in its planned task) owns mount/unmount and boot/
network ordering; the backend remains the non-root `nostalgia` process. Credential files are
root-owned mode `0600`, passed through CIFS credential-file configuration, and referenced by opaque
ID only.

Comparison:

| Option | Assessment |
| --- | --- |
| Direct application SMB library | Reject as primary: duplicates reconnect/auth/path semantics in Python, complicates MPV path access and exposes credentials to the backend process. |
| NostalgiaBox-managed OS CIFS mount | Preferred: one kernel filesystem view for scanner/ffprobe/MPV, mature reconnect/options, stable paths and systemd ordering. Requires a narrow privileged boundary. |
| Externally pre-mounted path | Supported expert/local-folder escape hatch, but cannot satisfy WebUI-managed credentials, testing or lifecycle by itself. |

Network loss causes source `unavailable`; it does not mark files missing. A successful remount and
scan reuses source/file identities. Mount commands never contain plaintext passwords.

## Scanner architecture

`ScanCoordinator` accepts a source ID, creates a durable run, and dispatches bounded work to an
in-process worker. Per-source mutual exclusion prevents overlapping scans. The worker uses ports:

- `SourceGateway` for availability and deterministic traversal;
- `MediaProbe` for typed ffprobe results;
- `ScanRepository`/`CatalogueRepository` for batch persistence;
- `ProgressSink` and injected clock/cancellation token.

### Safe execution sequence

1. Short transaction: validate source and create `queued` run.
2. Worker marks `running`, snapshots scan generation/configuration, then checks availability.
3. Traverse without a database transaction; normalize/validate paths and filter ignore rules.
4. Compare observations in pages. Skip probe for unchanged signatures; probe new/changed files
   outside transactions. Commit bounded, configurable idempotent batches. The default batch size is
   selected from Task 3.3 reference-Dell measurements.
5. Rate-limit durable progress updates using a configurable bounded cadence selected during
   implementation validation.
6. Only after complete enumeration, short final transaction marks previously known-but-unseen files
   missing and marks the run completed.
7. On cancel/process/error, record cancelled/interrupted/failed; never execute missing reconciliation.

Full scan enumerates all eligible files. Incremental scan still verifies the source view but avoids
reprobing unchanged signatures; later platform watchers may only trigger scans, never become the
sole source of truth. Symlinks are not followed by default; mount boundaries, hidden/system/cache
directories and configurable ignore patterns are enforced.

On startup, stale `running` runs become `interrupted`. Re-running is safe because observations and
batches are keyed by stable IDs/generation. Cancellation is cooperative between files/subprocesses.

## ffprobe boundary and format state

`FfprobeAdapter` executes an explicit binary with an argument array, timeout, bounded captured
output and no shell. It requests JSON (`-show_format`, `-show_streams`) and maps it into typed values.
The adapter records ffprobe version/capability separately and never stores raw stdout as domain data.

Captured values include duration in exact microseconds, format names, codecs, width/height, rational
frame-rate numerator/denominator, language/disposition and audio/subtitle stream summaries. Timeout
kills the child process. Exit failure, corrupt media, malformed/oversized JSON and missing binary
are distinct sanitized failures; stderr is redacted/truncated for diagnostics and not returned raw.

```text
discovered -> inspected -> compatible_candidate -> verified_playable
           \-> unsupported
           \-> inspection_failed
```

Extension controls discovery only. Compatibility is conservative and capability-versioned.
Verified playable requires actual successful player validation/evidence. Rich internet metadata is
outside this adapter and Phase 3.

## Matching and correction model

Filename parsing creates a `MatchCandidate` containing parsed title/year/series/season/episode,
parser version, evidence and confidence. It does not mutate identity. Basic deterministic patterns
handle common `S01E02`, `1x02`, season folders and movie-year names; ambiguous files remain unknown.

Derived editorial records and manual overrides are separate. Effective value precedence is:

```text
manual override / locked manual match
  > accepted derived match
  > normalized filename fallback
  > original basename
```

Measured technical facts are not in this precedence chain. Optimistic revision numbers prevent two
browser sessions silently overwriting corrections. Clearing an override exposes current derived
data. Rescan/reprobe may refresh candidates but cannot modify locked mappings or overrides.

## Artwork boundary

The DB stores only `ArtworkReference` ownership, provenance and cache key/status. Rebuildable files
live under `/var/cache/nostalgiabox/artwork`. A missing image returns a placeholder and issue, never
a catalogue or playback failure. Phase 3 does not add cloud artwork providers. Administrator-
uploaded persistent originals are deferred unless a later reviewed requirement establishes a need;
they are not a Phase 3 acceptance blocker.

## Proposed database design

All IDs are stable strings; timestamps are aware UTC encoded using the existing exact convention.
Every schema change is a new Alembic revision.

| Table | Important columns and constraints/indexes |
| --- | --- |
| `media_sources` | `id PK`, `kind`, unique normalized `name`, `root_config`, `enabled`, availability fields, `credential_ref`, last-check/successful-scan IDs/times, soft-retire time; index enabled/state. No secret value. |
| `media_items` (unchanged compatibility table) | Existing `id`, `title`, `duration_us`, `path`; existing timeline FKs and Phase 2 runtime access remain intact in Task 3.1. |
| `catalogue_items` | `id PK`, item kind, effective/derived editorial fields, lifecycle/revision timestamps. Existing media IDs are backfilled unchanged; rows need not yet be playable. |
| `series` | `id PK`, title/sort title; normalized-title index. |
| `seasons` | `id PK`, `series_id FK RESTRICT`, number/title; unique `(series_id, number)`. |
| `movie_details` | `catalogue_item_id PK/FK CASCADE`, year and optional editorial fields. |
| `episode_details` | `catalogue_item_id PK/FK CASCADE`, `season_id FK RESTRICT`, episode number/part; unique season numbering where known. |
| `media_files` | `id PK`, `source_id FK RESTRICT`, normalized/original relative path, size, mtime, optional device/inode and fingerprints, observation/probe/playability states, seen/missing/retired fields, revision; unique active `(source_id, normalized_relative_path)` and indexes on source/state/signature/fingerprint. |
| `technical_metadata` | `media_file_id PK/FK CASCADE`, duration, containers/codecs, dimensions/frame-rate, probe version/time/signature. |
| `media_streams` | `id PK`, `media_file_id FK CASCADE`, stream index/type/codec/language/channels/disposition; unique `(media_file_id, stream_index)`. |
| `media_matches` | Provenanced candidate/accepted matching between file and catalogue item; origin/confidence/locked/revision, separate from playback bounds. |
| `playable_renditions` | `catalogue_item_id FK RESTRICT`, `media_file_id FK RESTRICT`, whole-file flag, non-negative `segment_start_us`, positive `segment_duration_us`, explicit logical duration, preferred/status/revision; composite identity and indexes. Domain/service validation prevents invalid/out-of-bounds/accidentally overlapping segments. |
| `catalogue_overrides` | `catalogue_item_id PK/FK CASCADE`, explicit nullable override fields, revision/update audit fields. |
| `scan_runs` | `id PK`, `source_id FK RESTRICT`, kind/status/config generation/timestamps/progress counters/error code; indexes source/time/status and one-active-run enforcement in service plus DB-supported guard. |
| `scan_issues` | `id PK`, `scan_id FK CASCADE`, optional file ID/path-safe reference, category/code/message/retryable/resolved time; index scan/category/resolution. |
| `content_fingerprints` / `duplicate_candidates` | Algorithm/version/digest/strength and pair/group review status; indexes algorithm/digest without asserting equivalence from weak hashes. |
| `artwork_references` | `id PK`, `catalogue_item_id FK CASCADE`, kind/provenance/cache key/status; index item/kind. |
| `admin_users`, `admin_sessions` | Username, password hash parameters, session digest/expiry/revocation; no plaintext credentials/tokens. |

Source root configuration should be normalized into typed columns/validated JSON only where source
variants genuinely differ; schema implementation must not use an unvalidated arbitrary options bag.
Secrets are excluded. Deleting logical items referenced by timelines uses `RESTRICT`.

## API architecture

Prefix all product routes with `/api/v1`; retain Phase 2 health/runtime compatibility.

```text
POST/GET/PATCH/DELETE /api/v1/sources[/<id>]
POST                    /api/v1/sources/<id>/test
POST/GET                /api/v1/scans, /api/v1/scans/<id>
GET                     /api/v1/scans/<id>/issues
GET                     /api/v1/catalogue
GET                     /api/v1/catalogue/<id>
GET                     /api/v1/catalogue/attention
PUT/DELETE              /api/v1/catalogue/<id>/overrides
PUT/DELETE              /api/v1/files/<id>/match
GET                     /api/v1/system/health, /api/v1/system/storage
POST/DELETE              /api/v1/auth/setup|login|logout
GET                      /api/v1/auth/session
```

Creates return `201`; scan start returns `202` plus scan ID; optimistic edits use revision/ETag and
return `409` on conflict. Removal is retire-by-default. Pagination uses opaque cursors and bounded
page sizes. Error envelope:

```json
{"error":{"code":"source.unavailable","message":"…","correlation_id":"…","retryable":true,"fields":{}}}
```

DTOs use stable IDs/enums, UTC timestamps and safe display paths. Pydantic/FastAPI concerns stop at
the route boundary. An OpenAPI-generated or schema-checked TypeScript client prevents handwritten
contract drift.

## WebUI architecture

React + TypeScript + Vite is a separate `frontend/admin` client. Suggested boundaries:

```text
src/app        router, providers, shell
src/api        generated contracts/client, error mapping
src/features   sources, scans, catalogue, attention, auth, system
src/components reusable presentation/accessibility components
src/test       API fixtures and browser helpers
```

Routes: `/setup`, `/login`, `/`, `/sources`, `/sources/:id`, `/scans/:id`, `/library`,
`/attention`, `/library/:id`, `/system`. Server state uses one query/cache layer; URL owns filters
and pagination; forms own draft state. Components do not infer scan/match policy. Initial progress
uses visibility-aware configurable bounded polling with idle/error backoff and ETag/updated
timestamps; the cadence and pagination limits are selected from implementation measurements.
SSE/WebSocket is deferred until polling proves inadequate.

## Security architecture

- Bind only configured local interfaces; validate trusted hosts and same-origin requests. Setup
  starts in a restricted unclaimed state.
- A one-time random setup token is stored only as a digest, expires, is rate-limited and is destroyed
  on successful administrator creation. The physical/local delivery/reset mechanism is a required
  open decision before Task 3.11 exits; unauthenticated first-visitor takeover is not accepted.
- Hash passwords with Argon2id using versioned parameters. Store opaque random session tokens only
  as digests; cookies are HttpOnly, SameSite=Strict, narrowly scoped, rotated and time-limited.
  `Secure` is mandatory whenever HTTPS is configured; deployment documentation must not imply LAN
  HTTP protects confidentiality.
- Mutations require a CSRF token plus Origin/Host validation. Login/setup/source tests are rate
  limited. Authorization initially has one administrator role without precluding later roles.
- SMB credentials live in `/etc/nostalgiabox/credentials.d/<opaque-id>` mode `0600`, owned by root;
  session/bootstrap secrets use the same restricted secret boundary. A narrow privileged helper
  writes credential files and manages mounts. The API can replace/delete but never read a password.
- Structured logging uses codes, IDs and correlation IDs with central redaction; paths exposed to
  clients are display-safe source-relative values.

## Concurrency and SQLite

Use a bounded worker in the backend process, not a broker. The API enqueues durable DB work; the
worker owns scan execution and launches bounded ffprobe children. Process restart marks active runs
interrupted; a later implementation may split a worker process without changing application ports.

For production file-backed SQLite, Phase 3 has the concurrency requirement ADR-008 anticipated:
enable WAL after explicit migration/startup validation on the Dell, keep foreign keys enabled, set
a bounded busy timeout, use short read/write sessions, batch writes, and retry only transient busy
errors with a small bounded backoff. Do not enable WAL for in-memory tests or place the DB on NAS.
Benchmark playback reads, scan writes and API reads together before acceptance. Checkpoint behavior
and backup coordination remain operational concerns for later hardening; Phase 3 must at least test
restart and migration behavior with WAL sidecars handled outside Git.

## Failure and observability model

Application failures use the stable families in `REQUIREMENTS.md`, carry source/scan/file/catalogue
IDs, occurrence UTC, retryability and internal typed cause. Infrastructure detail and stack traces
remain internal. Scan issue records are durable and resolvable; transient source errors do not spam
one issue per retained file. Logs include action, duration/counts and correlation IDs but no secrets.

## Open decisions for architectural review

1. ADR-012's managed CIFS direction is approved; Task 3.6 must finalize and review the privileged-
   helper protocol, input allow-list, mount options, systemd boundary, permissions and reconnect
   lifecycle before the ADR can become Accepted.
2. ADR-013's authentication/secret direction is approved; Task 3.11 must finalize and review the
   first-run delivery/reset mechanism and privileged secret-helper boundary before acceptance.
3. Confirm initial extension allow-list and case-sensitivity behavior against the real internal/NAS
   libraries without using those libraries in automated tests.
4. Benchmark quick-fingerprint sampling size, scan batch size, worker/probe concurrency, WAL/busy
   timeout and catalogue pagination limits on the Dell rather than freezing speculative numbers.
