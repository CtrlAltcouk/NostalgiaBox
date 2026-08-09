# Phase 3 — Basic Media Catalogue and Administration Web UI: Test Plan

## Status

**Planned — 2026-08-09.** No Phase 3 test is marked PASS. Phase 2's 201-test Debian baseline remains
mandatory regression evidence; counts will change only as reviewed implementation lands.

Status vocabulary: `PLANNED`, `PASS`, `PARTIAL`, `FAIL`, `BLOCKED`, or
`DEFERRED-BY-APPROVED-SCOPE`.

## Test principles

- Unit tests use pure domain policies and fake source/probe/secret/mount/worker ports.
- Integration tests use temporary directory trees and migrated temporary SQLite databases.
- ffprobe process tests use controlled fixture executables/JSON; a small real ffprobe suite is
  isolated and platform-gated.
- Automated tests never use the owner's media/NAS, production DB/socket/mount, real credentials,
  `/var/lib/nostalgiabox`, or real `/dev/input`.
- Time, subprocess completion and worker scheduling are controllable; deterministic tests do not
  rely on arbitrary sleeps.
- Browser tests use disposable accounts/data and desktop/phone viewport projects.

## Requirement test matrix

| Area/scenario | Automated evidence required | Reference/manual evidence | Status |
| --- | --- | --- | --- |
| Phase 2 regression | Complete backend suite, architecture tests, migration compatibility | Debian full suite | PLANNED |
| Additive Phase 2 compatibility migration | Same-ID catalogue backfill; unchanged `media_items`, timeline FKs, runtime projection and lossless downgrade | Disposable Phase 2-shaped Dell DB | PLANNED |
| Catalogue item without rendition | Persist/query logical identity without creating a Phase 2 playable row | Not required | PLANNED |
| Initial local scan | Temporary tree → migrated DB → file/catalogue projections | Dell temporary local folder | PLANNED |
| Local allowed-root safety | Canonical containment, traversal/symlink/protected-root rejection and explicit expert-root allow-list | Dell approved-root permission smoke | PLANNED |
| Unchanged incremental scan | IDs/revisions/probe calls unchanged | Measured no-op scan | PLANNED |
| File addition | New file and metadata visible once | Local and NAS fixture | PLANNED |
| File removal | Successful complete scan marks missing, never deletes logical item | Local fixture | PLANNED |
| Rename/move | Unique strong evidence preserves file ID/match/override | Local and same-share rename | PLANNED |
| Changed/replaced file | Reprobe; replacement gets new file identity when content conflicts | Generated replacement | PLANNED |
| Duplicate | Weak candidate stays separate; full confirmation groups without deletion | Copy across source fixtures | PLANNED |
| Ambiguous fingerprint/collision | No silent merge; attention issue emitted | Not required—synthetic collision | PLANNED |
| Corrupt file | Probe failure stored/safely displayed | Small operator-owned corrupt fixture | PLANNED |
| Unsupported extension/content | Visible rejected/unsupported state and reason | Representative safe fixture | PLANNED |
| ffprobe success | Exact duration/container/streams/rational fields | Real ffprobe on Dell | PLANNED |
| ffprobe timeout/failure/malformed output | Typed categories, child cleanup, bounded output, redaction | Optional timeout smoke | PLANNED |
| Probe capability/version refresh | Changed version triggers refresh; unchanged does not | Dell installed version recorded | PLANNED |
| Source offline before scan | Prior files retained; availability issue, no missing reconciliation | NAS disconnect | PLANNED |
| NAS authentication/permission failure | Distinct safe categories, secret absent from output | Test account/permissions | PLANNED |
| NAS reconnect | Same source/file/catalogue IDs restored | Disconnect/reconnect test share | PLANNED |
| Interrupted scan | Stale run interrupted; rerun idempotent; unseen files not missing | Terminate isolated scan/restart | PLANNED |
| Cancellation | Committed batches valid; no final missing sweep | UI/API cancellation if implemented | PLANNED |
| Manual correction survives rescan | Override and locked match beat refreshed derived data | Browser correction then rescan | PLANNED |
| Clear correction | Latest derived value becomes effective | Browser flow | PLANNED |
| Concurrent edit | Revision conflict, no lost update | Two browser sessions optional | PLANNED |
| Multiple renditions | One logical item, deterministic available preferred file | Local/NAS copies | PLANNED |
| Whole-file rendition | Zero origin and validated physical/logical duration | Known-duration fixture | PLANNED |
| Multi-episode segments | One physical file, distinct catalogue IDs/ranges; invalid, zero, negative, out-of-bounds and accidental overlap rejected | Manual segment smoke with operator fixture | PLANNED |
| Segment playback projection | Resolver returns path/origin/logical bound; physical seek equals origin plus logical offset outside React/timeline | FakePlayer integration | PLANNED |
| Rendition duration discrepancy | Needs Attention issue; preferred rendition change does not mutate `MediaItem.duration` or existing timeline boundaries | Optional browser inspection | PLANNED |
| Unavailable preferred rendition | Controlled alternate selection or explicit unavailable result per policy | NAS loss during lookup | PLANNED |
| Playback while scanning | Runtime reads/MPV fake continue during batched writes | Real MPV playback during scan | PLANNED |
| Concurrent WebUI reads | Bounded latency/no lock failures while scan writes | Desktop/phone browse during scan | PLANNED |
| SQLite busy/retry bounds | Transient busy recovers; persistent busy fails safely | Dell WAL/busy benchmark | PLANNED |
| Migration lifecycle | Empty and Phase-2 DB additive upgrade/current/repeat/downgrade/re-upgrade with unchanged compatibility rows/FKs | Disposable Dell DB | PLANNED |
| Source API | Validation, lifecycle, test, redaction, status codes | Live API smoke | PLANNED |
| Scan API | 202/job ID, progress/history/issues, conflict/cancel | Live scan polling | PLANNED |
| Catalogue API | Pagination/search/filter/detail/attention/corrections/ETag | Live browser use | PLANNED |
| Stable error envelope | Code/message/correlation/retry/fields; no stack/secret | Inspect failure responses | PLANNED |
| Setup/auth/session | Token expiry/use-once, password hash, login/logout/revoke | First-run Dell flow | PLANNED |
| CSRF/Host/Origin/rate limiting | Positive/negative security suite | LAN deployment smoke | PLANNED |
| Secret storage | Fake adapter and permission/redaction audit | Dell file ownership/mode audit | PLANNED |
| WebUI desktop | Complete setup/source/scan/library/correction workflow | Current desktop browsers | PLANNED |
| WebUI phone | Responsive equivalent workflow and touch targets | Current phone browser | PLANNED |
| Accessibility | Automated rules plus keyboard/focus/error semantics | Manual keyboard/contrast review | PLANNED |
| Source deletion/retirement | Non-destructive default and FK-protected purge | Browser/API confirmation | PLANNED |
| Artwork absent/failure | Placeholder; no scan/playback failure | Browser smoke | PLANNED |
| Secrets/artifacts | Git audit for media/DB/WAL/cache/log/token/env/build output | Appliance paths outside checkout | PLANNED |

## Layering and contract tests

Maintain executable checks that:

- catalogue domain imports no FastAPI, SQLAlchemy, filesystem, subprocess, mount or React concepts;
- application services depend on typed repository/source/probe/secret/worker ports only;
- persistence imports no ffprobe/CIFS/MPV/UI code;
- scanner does not import API routes, player or timeline implementation;
- segment/rendition selection stays behind the application playback-location port and does not enter
  React or the pure timeline domain;
- ffprobe/CIFS adapters contain infrastructure syntax and return typed application values;
- API routes contain no ORM session, traversal, mount, ffprobe or matching policy;
- TypeScript client contracts match checked OpenAPI and contain no authoritative matching rules;
- existing Phase 2 domain/application dependency checks remain passing; no circular imports exist.

## Performance and concurrency budgets to establish

Task 3.11 must record Dell measurements before final thresholds are accepted:

- API catalogue read latency during idle and active scan;
- scan enumeration/probe throughput and CPU/memory load;
- MPV playback continuity/frame/audio observations during scan;
- SQLite busy count/retry time, WAL growth/checkpoint behavior;
- progress-write rate and WebUI polling request rate;
- representative small/medium library pagination/search response.

The architecture sets bounded behavior now; numerical pass thresholds require measured baseline and
review rather than invented values.

## Security test notes

- Never snapshot/log a real password, setup token, session cookie, CIFS username/password or
  credential file.
- Test cookies for HttpOnly/SameSite/path/expiry and Secure under HTTPS configuration.
- Verify mutation rejection for missing/invalid CSRF, hostile Origin/Host and expired/revoked session.
- Verify login/setup/source-test rate limits without making availability dependent on client IP alone.
- Verify API, logs, scan issues and frontend errors redact subprocess stderr and secrets.

## Reference-Dell/NAS acceptance sequence

Use isolated temporary sources, a least-privilege test share/account and operator-owned test media:

1. install/migrate from a Phase 2-shaped disposable DB and run all automated quality suites;
2. complete first-run authentication from desktop and phone using the approved token-delivery path;
3. add/test/scan a temporary local folder and test SMB share;
4. prove unchanged, add, change, rename, duplicate and remove behavior;
5. inspect known-good, corrupt and unsupported files through real ffprobe;
6. correct a match, rescan, disconnect/reconnect NAS and prove IDs/correction persist;
7. keep real MPV playback active while scanning and browsing from both clients;
8. interrupt/restart an isolated scan and prove safe recovery;
9. inspect source errors, Needs Attention, health, structured logs and secret-file permissions;
10. remove test sources/mounts/credentials and confirm no repository/runtime artifacts were created.

Do not repeat Phase 2 hardware scenarios unless the Phase 3 change can affect them; reuse accepted
display/audio/input evidence and focus on catalogue concurrency and source-path continuity.

## Phase 3 exit review

Closure requires a requirement-to-evidence traceability audit, all unapproved `PARTIAL`/`FAIL`
items resolved or reported as blockers, full backend/frontend quality suites, clean migrations,
reference Dell/NAS/browser evidence, security/artifact audit, documented performance measurements,
and confirmation that no Phase 4 scheduling or Phase 5 TV UI behavior was introduced.
