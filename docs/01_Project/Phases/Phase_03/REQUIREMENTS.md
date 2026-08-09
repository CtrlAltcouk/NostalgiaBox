# Phase 3 — Basic Media Catalogue and Administration Web UI: Requirements

## Status and purpose

**Planning status: In progress — 2026-08-09.** This document defines Phase 3 acceptance before
production implementation begins. No Phase 3 implementation task is complete.

Phase 3 makes local-folder and SMB/NAS media manageable through a local administration WebUI. It
extends the accepted Phase 2 core: the backend remains authoritative, catalogue identity—not a UI
path—feeds playback, and timeline/playback code remains independent of scanning and presentation.

## Scope and terminology

- A **source** is a configured local folder or managed SMB/NAS share.
- A **media file** is one observed physical file within a source.
- A **catalogue item** is a logical programme, movie or episode that can have several files.
- **Technical metadata** is measured from a file; **editorial metadata** describes the programme.
- A **scan** is a durable, restart-safe observation of one source.
- An **override** is an administrator correction that wins over derived matching data.

## Functional requirements

### P3-CAT — Catalogue and identity

1. `P3-CAT-01` The catalogue must distinguish sources, physical files, logical catalogue items,
   technical metadata, matches and user overrides.
2. `P3-CAT-02` Existing Phase 2 `MediaItem` IDs must remain valid stable logical identities for
   timeline/playback references through migration.
3. `P3-CAT-03` Absolute paths must never be catalogue identity. Source-relative paths are locators.
4. `P3-CAT-04` A catalogue item may have zero, one or several file renditions/locations; a file may
   be unmatched, linked to one item, or explicitly linked to several items where a multi-episode
   file is confirmed.
5. `P3-CAT-05` Identity must survive an unchanged rescan, a confidently detected rename/move,
   source reconnect and metadata correction.
6. `P3-CAT-06` Ambiguous identity evidence must create a review issue rather than silently merge
   records. Routine scans must not require whole-file hashing.
7. `P3-CAT-07` Duplicate candidates and confirmed duplicates must remain visible as distinct file
   locations; deduplication must not delete user media.
8. `P3-CAT-08` Missing files, temporarily unavailable files, unsupported files and failed probes
   must remain distinguishable and inspectable.

### P3-SRC — Media sources

1. `P3-SRC-01` Phase 3 must support enabled/disabled internal/local folders and SMB/NAS sources.
2. `P3-SRC-02` A source has stable generated identity, display name, type, configured root, enabled
   state, availability state, last check, last successful scan and sanitized current error.
3. `P3-SRC-03` Availability and scan execution are separate states. Disabling or losing a source
   must not classify every file as deleted.
4. `P3-SRC-04` Source tests must distinguish unreachable host, authentication failure, permission
   denial and invalid root where the adapter can do so safely.
5. `P3-SRC-05` Source removal must be explicit and non-destructive by default: retire the source and
   locations while retaining catalogue identities, corrections and referenced items. Hard purge is
   a separate reviewed operation and must respect foreign keys.
6. `P3-SRC-06` SMB credentials must never be returned by APIs, stored in ordinary catalogue rows,
   logged, committed to Git or passed in command arguments.

### P3-SCAN — Discovery, probing and reconciliation

1. `P3-SCAN-01` Scanning is an application service behind source, probe, persistence and progress
   ports; API routes and React components must not traverse filesystems.
2. `P3-SCAN-02` Full and incremental scans must find additions, unchanged files, modifications,
   confidently detectable moves/renames, missing files and duplicate candidates.
3. `P3-SCAN-03` Only a successfully completed source enumeration may mark unseen records missing.
   An unavailable source or interrupted scan must preserve the prior known state.
4. `P3-SCAN-04` Enumeration and ffprobe work occur outside long SQLite transactions. Results are
   committed in bounded, idempotent batches and final reconciliation is a short transaction.
5. `P3-SCAN-05` A durable scan run records status, counts, progress, timestamps, cancellation or
   interruption and structured issues. An abandoned running scan must become interrupted on
   recovery and be safely restartable.
6. `P3-SCAN-06` Playback must continue and catalogue reads must remain responsive while scanning.
7. `P3-SCAN-07` At most one active scan per source is allowed. Global probe/traversal concurrency
   must be bounded for the reference appliance.
8. `P3-SCAN-08` Cancellation may stop future work but must not roll back already committed valid
   batches or mark unseen files missing.
9. `P3-SCAN-09` Ignore rules, symlink policy, supported extensions and hidden/system directories
   must be explicit, deterministic and visible to diagnostics.

### P3-PROBE — Technical metadata and format policy

1. `P3-PROBE-01` ffprobe must be invoked through a typed infrastructure adapter using structured
   JSON output; domain/application code must not parse shell output.
2. `P3-PROBE-02` Captured facts include exact duration, container, video/audio codecs, dimensions,
   rational frame rate, audio streams and subtitle streams where present.
3. `P3-PROBE-03` Probe timeout, executable/version failure, non-zero exit, malformed JSON, corrupt
   media and unsupported content must produce controlled, sanitized issues.
4. `P3-PROBE-04` Metadata refresh occurs for a new/replaced file, a changed observation signature,
   explicit administrator request or probe-capability-version change—not every unchanged scan.
5. `P3-PROBE-05` The catalogue distinguishes discovered, inspected, compatible candidate, verified
   playable, unsupported and inspection-failed states. Probe success alone must not be overstated as
   proof of playback.
6. `P3-PROBE-06` Failed and unsupported files remain visible in Needs Attention.

### P3-MATCH — Logical media and manual corrections

1. `P3-MATCH-01` Basic matching must support movie, series, season, episode and unknown items.
2. `P3-MATCH-02` Filename parsing produces candidates and confidence/provenance only; it is never
   physical or logical identity.
3. `P3-MATCH-03` Fallback title order is user override, accepted derived title, normalized filename,
   then the original basename.
4. `P3-MATCH-04` Physical facts and editorial fields remain separate. Technical duration/codecs
   cannot be overwritten as if they were user-entered editorial data.
5. `P3-MATCH-05` A manual mapping or field override survives rescan, reprobe, rename, temporary
   source loss and lower-priority matcher output until explicitly cleared.
6. `P3-MATCH-06` Precedence is: explicit user override/locked mapping; accepted matcher result;
   filename fallback. Technical metadata remains authoritative for measured file facts.
7. `P3-MATCH-07` Clearing an override reveals the latest valid derived value rather than deleting
   scan facts.

### P3-ART — Artwork

1. `P3-ART-01` Basic optional artwork references may be associated with catalogue items.
2. `P3-ART-02` Artwork cache files are rebuildable state outside Git and outside the database.
3. `P3-ART-03` Missing or failed artwork must never block scanning, identity, timeline generation
   or playback.

### P3-API — Administration API

1. `P3-API-01` Versioned FastAPI routes call application services and return DTOs; routes never own
   ORM sessions, filesystem traversal, mount commands, ffprobe invocation or business matching.
2. `P3-API-02` The API supports source lifecycle/test operations, scan start/status/history/issues,
   catalogue search/detail/attention views, corrections, and basic storage/appliance health.
3. `P3-API-03` Long operations return a durable operation/scan ID and progress is initially polled.
4. `P3-API-04` Lists are paginated and filterable. Responses do not expose credentials, stack
   traces, unrestricted server paths or probe stderr.
5. `P3-API-05` Errors use a stable envelope containing machine code, safe message, correlation ID,
   retryability and optional field errors.
6. `P3-API-06` OpenAPI remains the contract source for a typed frontend client.

### P3-UI — Administration WebUI

1. `P3-UI-01` Use React, TypeScript and Vite as accepted by ADR-011. This is not the television UI.
2. `P3-UI-02` The initial sitemap includes Dashboard, Media Sources, Scan Status, Media Library,
   Needs Attention, Media Detail/Correction, System/Health and Setup/Authentication.
3. `P3-UI-03` Business rules and authoritative state remain in application services. Components own
   rendering, local form state and interaction only.
4. `P3-UI-04` Desktop and phone layouts must support first-run setup, source management, scanning,
   progress/errors and corrections without Linux or terminal access.
5. `P3-UI-05` Loading, empty, stale, partial-failure, offline and retry states must be explicit.
6. `P3-UI-06` Accessibility includes keyboard navigation, labelled controls, visible focus,
   sufficient contrast and non-colour-only status.

### P3-SEC — Local-first security and secrets

1. `P3-SEC-01` Administration is authenticated and limited to configured local interfaces/networks
   by default; internet exposure is unsupported without an explicitly reviewed reverse proxy/TLS.
2. `P3-SEC-02` First-run claim uses a one-time high-entropy setup token with expiry and rate
   limiting. Token delivery must require local/physical administrator access and be finalized before
   the security implementation task exits.
3. `P3-SEC-03` Passwords use a memory-hard password hash. Authentication uses opaque server-side
   sessions with revocation, expiry and secure cookie attributes appropriate to the deployment.
4. `P3-SEC-04` Mutating cookie-authenticated requests require CSRF protection and strict Origin/Host
   validation. CORS is deny-by-default/same-origin.
5. `P3-SEC-05` Share credentials and session-signing secrets live in permission-restricted files or
   a dedicated secret boundary outside the catalogue DB; DB rows hold opaque references only.
6. `P3-SEC-06` Logs, API errors, audit data and support output redact credentials, tokens, cookies
   and sensitive path/user components.
7. `P3-SEC-07` Authentication, setup and source-test endpoints are rate limited and auditable
   without recording secret material.

### P3-CON — SQLite and execution model

1. `P3-CON-01` Keep one operational backend and no Redis/Celery/message broker. A bounded in-process
   worker executes scans; ffprobe remains a supervised child process behind its adapter.
2. `P3-CON-02` The live SQLite database remains local to the appliance and backend-owned.
3. `P3-CON-03` Production file-backed SQLite uses short transactions, foreign keys, WAL after Dell
   validation, a bounded busy timeout and narrowly bounded retry for transient busy errors.
4. `P3-CON-04` API request handlers must not block the event loop with traversal, probing or long
   synchronous database work.
5. `P3-CON-05` Progress publication must not turn every discovered file into an unbounded write or
   client update.

## Failure categories

The application taxonomy must distinguish at least:

| Code family | Examples |
| --- | --- |
| `source.*` | unavailable, authentication, permission, invalid root, mount failure |
| `scan.*` | already running, interrupted, cancelled, traversal failure, database failure |
| `file.*` | disappeared, unsupported, replaced, possible duplicate |
| `probe.*` | unavailable/version, timeout, process failure, malformed output, corrupt media |
| `match.*` | ambiguous, invalid correction, stale edit/conflict |
| `auth.*` | setup required, invalid credentials, expired session, CSRF/rate limit |

Failures shown to users must be actionable and correlation-addressable without stack traces.

## Initial format policy

The initial discovery allow-list is configurable and begins with common video containers:
`.mkv`, `.mp4`, `.m4v`, `.avi`, `.mov`, `.webm`, `.mpg`, `.mpeg`, `.ts`, and `.m2ts`.
Extension makes a file discoverable, not known playable. ffprobe inspection and a conservative
capability policy may classify it as a compatible candidate; only successful MPV use or an
equivalent validation may classify a rendition as verified playable. Unknown/failed files remain
visible rather than silently disappearing.

## Non-functional requirements

- Operation is local-first and does not require cloud metadata or an internet connection.
- Automated tests use temporary filesystems/databases and fake source/probe adapters, never the
  owner's media, NAS, production database, real credentials or production mounts.
- Scan operations are idempotent, observable and recoverable after process interruption.
- Catalogue list/search remains responsive at the expected household-library scale; performance
  budgets must be measured on the Dell before closure.
- UTC-aware timestamps and Phase 2 structured diagnostics rules remain authoritative.
- User media, databases, cache files, credentials and generated artifacts remain outside Git.

## Explicit non-goals

Phase 3 does not implement USB hot-plug polish, Plex/Jellyfin, cloud metadata providers, advanced
artwork management, editable multi-channel scheduling, channel pools, TV overlay/EPG, remote TV
navigation, production systemd service units, installer/updater, backup/restore or Phase 4/5 work.

## Exit criteria

Phase 3 completes only when local and SMB/NAS sources can be safely configured, scanned and
reconciled; logical matches and durable corrections are manageable through authenticated desktop
and phone WebUI; playback consumes stable catalogue IDs; concurrent playback/scan/read behavior is
validated; migrations and recovery pass; secrets/artifacts remain protected; Dell and real-NAS/
ffprobe evidence is recorded; and all requirements trace to passing tests or approved deferral.
