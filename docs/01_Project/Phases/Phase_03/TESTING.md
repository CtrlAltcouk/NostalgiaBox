# Phase 3 — Basic Media Catalogue and Administration Web UI: Test Plan

## Status

**In progress — 2026-08-10.** Tasks 3.1 and 3.2 are `PASS` for their approved scope. Task 3.3
development validation passes 348 tests on Windows/Python 3.13 with five honest capability skips;
its isolated reference-Dell validation remains pending. Task 3.4 has not started, and Phase 3 as a
whole remains in progress.

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
| Phase 2 regression | Complete backend suite, architecture tests, migration compatibility | Latest Debian full suite: 291 passed, no skips, including AF_UNIX | PASS |
| Additive Phase 2 compatibility migration | Same-ID catalogue backfill; unchanged `media_items`, timeline FKs, runtime projection and lossless downgrade | Disposable Phase 2-shaped Dell DB lifecycle passed | PASS |
| Catalogue item without rendition | Persist/query logical identity without creating a Phase 2 playable row | Not required | PASS |
| Historical file identity at reused locator | Two stable `MediaFile` IDs may share one source/normalized locator; composite lookup index is non-unique; blank IDs/locators fail DB checks | Not required | PASS |
| One present file per source/locator | `PRESENT` partial unique index; `UNCLASSIFIED`/`MISSING` duplicates remain legal; ambiguous legacy rows are not merged | Repeat constraint/migration suite on Dell | PARTIAL |
| Local source create/read/edit/test/enable/disable | Pure service, unit-of-work/revision conflicts, real temporary-root adapter and exact persistence round trip pass | Dell readable/missing source lifecycle passed as `nostalgia` | PASS |
| Local availability and diagnostics | Enabled/availability remain independent; permission/invalid/unavailable mapping, recovery clearing and exact UTC check pass | Real mode-`000` permission denial as `nostalgia` returned `PERMISSION_DENIED` | PASS |
| Initial local scan | Real temporary-tree adapter → one `PRESENT` physical row per eligible file; no logical/playable rows | Dell temporary local folder pending | PARTIAL |
| Local allowed-root safety | Canonical containment, traversal/sibling-prefix/protected-root rejection, explicit expert allow-list and same-root/escape symlink policy implemented | Dell real symlink, retarget, traversal and permission cases passed | PASS |
| Unchanged incremental scan | Same IDs/signatures, no duplicates, unchanged count and successful-scan advance pass | Dell no-op rescan pending; probe skipping belongs to 3.4 | PARTIAL |
| File addition | Existing ID retained and one new `PRESENT` physical ID created | Dell generated local fixture pending; NAS later | PARTIAL |
| File removal | Only successful authoritative scan marks retained row `MISSING`; failed/cancelled/source-changed scans do not | Dell generated local fixture pending | PARTIAL |
| Rename/move | Unique strong evidence preserves file ID/match/override | Local and same-share rename | PLANNED |
| Changed observation at same locator | Cheap signature change detected, provisional ID retained and safe issue emitted; no replacement claim | Dell generated change pending; Task 3.5 owns final identity | PARTIAL |
| Duplicate | Weak candidate stays separate; full confirmation groups without deletion | Copy across source fixtures | PLANNED |
| Ambiguous fingerprint/collision | No silent merge; attention issue emitted | Not required—synthetic collision | PLANNED |
| Corrupt file | Probe failure stored/safely displayed | Small operator-owned corrupt fixture | PLANNED |
| Unsupported extension/content | Visible rejected/unsupported state and reason | Representative safe fixture | PLANNED |
| ffprobe success | Exact duration/container/streams/rational fields | Real ffprobe on Dell | PLANNED |
| ffprobe timeout/failure/malformed output | Typed categories, child cleanup, bounded output, redaction | Optional timeout smoke | PLANNED |
| Probe capability/version refresh | Changed version triggers refresh; unchanged does not | Dell installed version recorded | PLANNED |
| Source offline before scan | Controlled availability failure, prior files and successful-scan time retained, no traversal/reconciliation | Local fake passes; NAS disconnect belongs later | PARTIAL |
| NAS authentication/permission failure | Distinct safe categories, secret absent from output | Test account/permissions | PLANNED |
| NAS reconnect | Same source/file/catalogue IDs restored | Disconnect/reconnect test share | PLANNED |
| Interrupted scan/recovery | Failed traversal retains committed batches; abandoned queued/running runs become interrupted idempotently; unseen files stay present | Dell focused suite and recovery smoke pending | PARTIAL |
| Cancellation | Durable repeated request is safe; committed batch remains; no final missing sweep/success timestamp | Dell focused cancellation case pending; API later | PARTIAL |
| One active scan per source | Application guard plus SQLite partial unique active-source index; different sources admitted within executor bound | Dell focused constraint/worker proof pending | PARTIAL |
| Manual correction survives rescan | Override and locked match beat refreshed derived data | Browser correction then rescan | PLANNED |
| Clear correction | Latest derived value becomes effective | Browser flow | PLANNED |
| Concurrent edit | Revision conflict, no lost update | Two browser sessions optional | PLANNED |
| Multiple renditions | One logical item, deterministic preferred lookup and one-preferred constraint pass | Local/NAS selection policy belongs to later tasks | PARTIAL |
| Whole-file rendition | Zero origin and validated physical/logical duration pass | Not required for pure Task 3.1 foundation | PASS |
| Multi-episode segments | One physical file, distinct catalogue IDs/ranges; invalid, zero, negative, out-of-bounds and accidental overlap rejected | Later operator-fixture smoke remains | PARTIAL |
| Segment playback projection | Pure resolver value returns path/origin/logical bound; physical position equals origin plus logical offset outside React/timeline | Runtime integration deliberately deferred; Phase 2 runtime unchanged | PARTIAL |
| Rendition duration discrepancy | Needs Attention issue; preferred rendition change does not mutate `MediaItem.duration` or existing timeline boundaries | Optional browser inspection | PLANNED |
| Unavailable preferred rendition | Controlled alternate selection or explicit unavailable result per policy | NAS loss during lookup | PLANNED |
| Playback while scanning | Seeded Phase 2 runtime repeatedly resolves from same disposable DB during bounded scan writes | Dell same-DB runtime proof pending; real MPV concurrency later | PARTIAL |
| Concurrent WebUI reads | Bounded latency/no lock failures while scan writes | Desktop/phone browse during scan | PLANNED |
| SQLite busy/retry bounds | Transient busy recovers; persistent busy fails safely | Dell WAL/busy benchmark | PLANNED |
| Migration lifecycle | Task 3.3 empty/current/repeat/downgrade/re-upgrade and populated Task 3.2 lossless preservation pass; duplicate legacy locators remain `UNCLASSIFIED` | Task 3.2 evidence remains PASS; `20260810_0004` Dell lifecycle pending | PARTIAL |
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
| Source deletion/retirement | Source retirement is terminal, disables without deleting source/file/catalogue data; physical-location retirement/purge remains later work | Dell non-destructive source retirement and exact repository reload passed; physical-location lifecycle remains later | PARTIAL |
| Artwork absent/failure | Placeholder; no scan/playback failure | Browser smoke | PLANNED |
| Secrets/artifacts | Development Git audit for media/DB/WAL/cache/log/token/env/build output | Repeat checkout/appliance cleanup audit on Dell | PARTIAL |

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

### Task 3.1 isolated reference-Dell evidence — PASS

Validation completed on Debian 13 with Python 3.13.5 using the temporary detached worktree
`/tmp/nostalgiabox-task31`, an isolated virtual environment inside it and disposable SQLite data
under `/tmp`.

- Full `pytest`: **250 passed, no skips**. The Linux AF_UNIX integration path ran and passed; the
  full Phase 2 regression and Task 3.1 automated suite therefore pass on the reference appliance.
- Focused `test_catalogue_migration.py` plus `test_catalogue_repositories.py`: **19 passed**. This
  covers populated same-ID migration, exact Phase 2 media/timeline/FK preservation, repository and
  compatibility projection behavior, multi-episode/shared-file representation, distinct historical
  file IDs at one locator, absence of invented lifecycle state, SQLite integrity checks, rendition
  conflict/preferred rules and FK deletion protection.
- `ruff check .`: **PASS**.
- `ruff format --check .`: **PASS**, 92 files already formatted.
- `mypy`: **PASS**, no issues across 89 source files.
- Explicit Alembic lifecycle on a completely disposable database: empty upgrade through
  `20260808_0001` to `20260809_0002 (head)`, repeated head upgrade, downgrade to `20260808_0001`,
  and re-upgrade to `20260809_0002 (head)` all passed.

The disposable database and temporary worktree were removed after validation. The production
database and media library were not accessed, and MPV, boot/X, autologin and systemd configuration
were not modified. This evidence accepts only Task 3.1. Active-file locator uniqueness, source
lifecycle, scanning, ffprobe, fingerprints, reconciliation, SMB/NAS, matching, WebUI,
authentication and Phase 4 scheduling integration remain later work.

### Task 3.2 isolated reference-Dell evidence — PASS

Validation completed on Debian 13 with Python 3.13.5 from temporary worktree
`/tmp/nostalgiabox-task32`. It used an isolated virtual environment, disposable SQLite databases,
temporary directories beneath `/srv/nostalgiabox/media/task32-validation` and a temporary
outside-root directory under `/tmp`. The production database was not modified, no production media
was scanned, and MPV, playback, boot/X, autologin and systemd configuration were untouched.

- Full `pytest`: **291 passed, no skips**. Phase 2 and Task 3.1 regressions passed. Linux AF_UNIX,
  both real symlink-capability cases and the real POSIX permission test all ran and passed.
- Focused Task 3.2 suite: **37 passed, no skips**. This covered approved-root containment and
  descendants; traversal, sibling-prefix, absolute-outside, protected-root and symlink escape
  rejection; same-root symlinks and retarget revalidation; controlled missing/non-directory and
  filesystem errors; real and deterministic permission classification; stable identity and root
  edit policy; availability invalidation/preservation; lifecycle, retirement, revisions,
  repositories and Task 3.1 migration compatibility.
- `ruff check .`: **PASS**. `ruff format --check .`: **PASS**, 102 files already formatted.
- `mypy`: **PASS**, no issues across 98 source files.
- Disposable Alembic lifecycle: empty upgrade through `20260808_0001` and `20260809_0002` to
  `20260810_0003 (head)`, repeat head, downgrade to `20260809_0002`, and re-upgrade to unchanged
  `20260810_0003 (head)`: **PASS**.
- Real source proof as `nostalgia`: create began `UNKNOWN` and enabled; check returned `AVAILABLE`;
  disable/enable changed only enabled state; a temporarily renamed root returned `INVALID_ROOT`
  while remaining enabled; a mode-`000` root returned `PERMISSION_DENIED`; an outside-root symlink
  was rejected with controlled `InvalidSourceRootError`; terminal retirement populated
  `retired_utc`, disabled the source and preserved an exactly reloadable repository row: **PASS**.
- Cleanup: temporary source/outside-root directories, hardware and migration databases, isolated
  environment and worktree were removed. Production NostalgiaBox data and appliance configuration
  were not altered.

The executed procedure was:

```bash
set -euo pipefail
git fetch origin
test ! -e /tmp/nostalgiabox-task32
git worktree add --detach /tmp/nostalgiabox-task32 \
  origin/codex/phase-3.2-local-source-lifecycle
cd /tmp/nostalgiabox-task32/backend
python3.13 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,linux-input]'

.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy
.venv/bin/python -m pytest -vv \
  tests/unit/source/test_local.py \
  tests/unit/application/test_sources.py \
  tests/integration/test_source_repositories.py \
  tests/integration/test_source_migration.py \
  tests/integration/test_migrations.py

# Explicit disposable Alembic lifecycle.
migration_root="$(mktemp -d /tmp/nostalgiabox-task32-migration.XXXXXX)"
export NOSTALGIABOX_ENVIRONMENT=test
export NOSTALGIABOX_DATABASE_URL="sqlite+pysqlite:///$migration_root/lifecycle.db"
.venv/bin/alembic upgrade head
.venv/bin/alembic current
.venv/bin/alembic upgrade head
.venv/bin/alembic downgrade 20260809_0002
.venv/bin/alembic current
.venv/bin/alembic upgrade head
.venv/bin/alembic current
unset NOSTALGIABOX_DATABASE_URL NOSTALGIABOX_ENVIRONMENT

# Real local-source proof as the production service account.
validation_root=/srv/nostalgiabox/media/task32-validation
hardware_db=/tmp/nostalgiabox-task32-hardware.sqlite3
outside_root=/tmp/nostalgiabox-task32-outside
test ! -e "$validation_root"
test ! -e "$hardware_db"
test ! -e "$outside_root"
sudo install -d -o nostalgia -g nostalgia -m 0700 \
  "$validation_root/readable" "$validation_root/unreadable" "$outside_root"
sudo -u nostalgia env \
  NOSTALGIABOX_ENVIRONMENT=test \
  NOSTALGIABOX_DATABASE_URL="sqlite+pysqlite:///$hardware_db" \
  .venv/bin/alembic upgrade head
sudo -u nostalgia env \
  NOSTALGIABOX_ENVIRONMENT=test \
  NOSTALGIABOX_DATABASE_URL="sqlite+pysqlite:///$hardware_db" \
  .venv/bin/python - <<'PY'
from pathlib import Path

from nostalgiabox.application.sources import InvalidSourceRootError, LocalSourceService
from nostalgiabox.config.settings import Settings
from nostalgiabox.domain import MediaSourceId, SourceAvailability, SystemClock
from nostalgiabox.persistence.catalogue_repositories import SqlAlchemyMediaSourceRepository
from nostalgiabox.persistence.database import create_engine, create_session_factory
from nostalgiabox.persistence.source_uow import SqlAlchemySourceUnitOfWork
from nostalgiabox.source.local import LocalFilesystemSourceGateway

root = Path("/srv/nostalgiabox/media/task32-validation")
readable = root / "readable"
unreadable = root / "unreadable"
outside = Path("/tmp/nostalgiabox-task32-outside")
database_url = "sqlite+pysqlite:////tmp/nostalgiabox-task32-hardware.sqlite3"
engine = create_engine(Settings(environment="test", database_url=database_url))
factory = create_session_factory(engine)
ids = iter((MediaSourceId("dell-readable"), MediaSourceId("dell-permission")))
gateway = LocalFilesystemSourceGateway([str(root)])
service = LocalSourceService(
    lambda: SqlAlchemySourceUnitOfWork(factory), gateway, SystemClock(), lambda: next(ids)
)

created = service.create_local_source("Dell readable", str(readable), enabled=True)
available = service.check_availability(created.id)
assert available.availability is SourceAvailability.AVAILABLE
disabled = service.disable_source(created.id, available.revision)
enabled = service.enable_source(created.id, disabled.revision)
assert not disabled.enabled and enabled.enabled

readable.rename(root / "readable-missing")
missing = service.check_availability(created.id)
assert missing.availability is SourceAvailability.INVALID_ROOT and missing.enabled
(root / "readable-missing").rename(readable)

permission_source = service.create_local_source(
    "Dell permission", str(unreadable), enabled=True
)
unreadable.chmod(0)
try:
    denied = service.check_availability(permission_source.id)
finally:
    unreadable.chmod(0o700)
assert denied.availability is SourceAvailability.PERMISSION_DENIED

escape = root / "escape"
escape.symlink_to(outside, target_is_directory=True)
try:
    gateway.validate_root(str(escape))
except InvalidSourceRootError:
    pass
else:
    raise AssertionError("outside-root symlink was accepted")

retired = service.retire_source(created.id, missing.revision)
assert retired.retired_utc is not None and not retired.enabled
with factory() as session:
    repository = SqlAlchemyMediaSourceRepository(session)
    assert repository.get_by_id(created.id) == retired
    assert not repository.has_media_files(created.id)
engine.dispose()
PY

# Remove every disposable artifact and worktree.
sudo -u nostalgia rm -r -- "$validation_root" "$outside_root"
sudo -u nostalgia rm -- "$hardware_db"
rm -r -- "$migration_root"
cd -
git worktree remove --force /tmp/nostalgiabox-task32
```

This evidence accepts the behavior owned by Task 3.2 only. Scanning, `MediaFile` active/missing/
retired state, physical-location retirement, active-only locator uniqueness, successful-scan
timestamps, SMB/NAS and credentials, APIs, WebUI and Task 3.3+ remain `PARTIAL` or `PLANNED` as
shown above. That was the Task 3.2 acceptance boundary; Task 3.3 is now implemented in development
as documented below. Phase 3 remains in progress and Task 3.4 has not started.

### Task 3.3 isolated reference-Dell procedure — pending

Run this exact procedure on Debian 13/Python 3.13 from a clean existing repository. It uses only
`/tmp`, a detached temporary worktree, disposable SQLite databases and the single temporary source
`/srv/nostalgiabox/media/task33-validation`. It must not scan the parent media root, access the
production database, or modify MPV, playback, boot/X, autologin or systemd configuration.

```bash
set -euo pipefail
git fetch origin
test ! -e /tmp/nostalgiabox-task33
test ! -e /srv/nostalgiabox/media/task33-validation
git worktree add --detach /tmp/nostalgiabox-task33 \
  origin/codex/phase-3.3-scan-coordinator-local-discovery
cd /tmp/nostalgiabox-task33/backend
python3.13 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,linux-input]'

.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy
.venv/bin/python -m pytest -vv \
  tests/unit/domain/test_scanning.py \
  tests/unit/source/test_traversal.py \
  tests/unit/source/test_executor.py \
  tests/integration/test_scan_coordinator.py \
  tests/integration/test_scan_repositories.py \
  tests/integration/test_scan_migration.py \
  tests/integration/test_migrations.py \
  tests/unit/test_architecture.py \
  tests/unit/test_settings.py

# Explicit disposable Alembic lifecycle.
migration_root="$(mktemp -d /tmp/nostalgiabox-task33-migration.XXXXXX)"
export NOSTALGIABOX_ENVIRONMENT=test
export NOSTALGIABOX_DATABASE_URL="sqlite+pysqlite:///$migration_root/lifecycle.db"
.venv/bin/alembic upgrade head
.venv/bin/alembic current
.venv/bin/alembic upgrade head
.venv/bin/alembic downgrade 20260810_0003
.venv/bin/alembic current
.venv/bin/alembic upgrade head
.venv/bin/alembic current
unset NOSTALGIABOX_DATABASE_URL NOSTALGIABOX_ENVIRONMENT

# Generate one tiny real source; never enumerate its parent.
validation_root=/srv/nostalgiabox/media/task33-validation
hardware_db=/tmp/nostalgiabox-task33-hardware.sqlite3
fake_bin="$(mktemp -d /tmp/nostalgiabox-task33-bin.XXXXXX)"
ffprobe_marker=/tmp/nostalgiabox-task33-ffprobe-invoked
test ! -e "$hardware_db"
test ! -e "$ffprobe_marker"
sudo install -d -o nostalgia -g nostalgia -m 0700 \
  "$validation_root/nested" "$validation_root/.hidden" "$validation_root/skip-cache"
sudo -u nostalgia sh -c 'printf one > "$1/one.mkv"' sh "$validation_root"
sudo -u nostalgia sh -c 'printf two > "$1/nested/two.MP4"' sh "$validation_root"
sudo -u nostalgia sh -c 'printf hidden > "$1/.hidden/hidden.mkv"' sh "$validation_root"
sudo -u nostalgia sh -c 'printf ignored > "$1/skip-cache/ignored.mkv"' sh "$validation_root"
sudo -u nostalgia sh -c 'printf text > "$1/notes.txt"' sh "$validation_root"
sudo -u nostalgia ln -s -- one.mkv "$validation_root/link.mkv"
cat > "$fake_bin/ffprobe" <<'SH'
#!/bin/sh
touch /tmp/nostalgiabox-task33-ffprobe-invoked
exit 99
SH
chmod 0755 "$fake_bin/ffprobe"
sudo -u nostalgia env \
  NOSTALGIABOX_ENVIRONMENT=test \
  NOSTALGIABOX_DATABASE_URL="sqlite+pysqlite:///$hardware_db" \
  .venv/bin/alembic upgrade head
sudo -u nostalgia env \
  PATH="$fake_bin:$PATH" \
  NOSTALGIABOX_ENVIRONMENT=test \
  NOSTALGIABOX_DATABASE_URL="sqlite+pysqlite:///$hardware_db" \
  NOSTALGIABOX_APPROVED_LOCAL_MEDIA_ROOTS='["/srv/nostalgiabox/media/task33-validation"]' \
  NOSTALGIABOX_SCAN_IGNORE_PATTERNS='["skip-*"]' \
  .venv/bin/python - <<'PY'
from pathlib import Path
from time import monotonic
from uuid import uuid4

from sqlalchemy import func, select

from nostalgiabox.application.scans import ScanCoordinator
from nostalgiabox.config.settings import Settings
from nostalgiabox.domain import (
    FilePresenceState,
    MediaFileId,
    MediaSource,
    MediaSourceId,
    MediaSourceKind,
    ScanIssueId,
    ScanKind,
    ScanRunId,
    ScanStatus,
    SystemClock,
)
from nostalgiabox.persistence.catalogue_mappers import media_file_from_record
from nostalgiabox.persistence.catalogue_repositories import SqlAlchemyMediaSourceRepository
from nostalgiabox.persistence.database import create_engine, create_session_factory
from nostalgiabox.persistence.models import (
    CatalogueItemRecord,
    MediaFileRecord,
    MediaItemRecord,
    PlayableRenditionRecord,
)
from nostalgiabox.persistence.scan_repositories import SqlAlchemyScanRunRepository
from nostalgiabox.persistence.scan_uow import SqlAlchemyScanUnitOfWork
from nostalgiabox.source.local import LocalFilesystemSourceGateway
from nostalgiabox.source.traversal import LocalFilesystemTraversalGateway


class InlineExecutor:
    def submit(self, operation):
        operation()

    def shutdown(self, *, wait=True):
        return None


settings = Settings()
root = Path("/srv/nostalgiabox/media/task33-validation")
engine = create_engine(settings)
factory = create_session_factory(engine)
source_id = MediaSourceId("dell-task33")
with factory() as session:
    SqlAlchemyMediaSourceRepository(session).store(
        MediaSource(
            source_id,
            MediaSourceKind.LOCAL,
            display_name="Task 3.3 validation",
            configured_root=str(root),
            enabled=True,
        )
    )
    session.commit()
source_gateway = LocalFilesystemSourceGateway([str(root)])
traversal = LocalFilesystemTraversalGateway(
    source_gateway,
    settings.scan_discovery_extensions,
    settings.scan_ignore_patterns,
)
coordinator = ScanCoordinator(
    lambda: SqlAlchemyScanUnitOfWork(factory),
    source_gateway,
    traversal,
    InlineExecutor(),
    SystemClock(),
    lambda: ScanRunId(str(uuid4())),
    lambda: ScanIssueId(str(uuid4())),
    lambda: MediaFileId(str(uuid4())),
    persistence_batch_size=settings.scan_persistence_batch_size,
    progress_update_threshold=settings.scan_progress_update_threshold,
)


def scan(kind=ScanKind.FULL):
    queued = coordinator.start_scan(source_id, kind)
    with factory() as session:
        run = SqlAlchemyScanRunRepository(session).get(queued.id)
        assert run is not None and run.status is ScanStatus.COMPLETED
        return run


def files():
    with factory() as session:
        records = session.scalars(
            select(MediaFileRecord)
            .where(MediaFileRecord.source_id == source_id.value)
            .order_by(MediaFileRecord.normalized_relative_locator)
        ).all()
        return tuple(media_file_from_record(record) for record in records)


started = monotonic()
initial = scan()
initial_files = files()
assert [item.normalized_relative_locator for item in initial_files] == [
    "nested/two.MP4",
    "one.mkv",
]
assert initial.counters.added == 2 and initial.counters.ignored == 4
initial_ids = {item.normalized_relative_locator: item.id for item in initial_files}

unchanged = scan(ScanKind.INCREMENTAL)
assert unchanged.counters.unchanged == 2
assert {item.normalized_relative_locator: item.id for item in files()} == initial_ids

(root / "added.m4v").write_bytes(b"added")
added = scan(ScanKind.INCREMENTAL)
assert added.counters.added == 1 and added.counters.unchanged == 2

(root / "one.mkv").write_bytes(b"one-changed")
changed = scan()
assert changed.counters.changed == 1
assert {item.normalized_relative_locator: item.id for item in files()}["one.mkv"] == initial_ids[
    "one.mkv"
]

removed_path = root / "nested/two.MP4"
removed_path.unlink()
removed = scan()
assert removed.counters.missing == 1
missing = next(item for item in files() if item.normalized_relative_locator == "nested/two.MP4")
assert missing.id == initial_ids["nested/two.MP4"]
assert missing.presence is FilePresenceState.MISSING

removed_path.write_bytes(b"two-restored")
scan()
restored = next(item for item in files() if item.normalized_relative_locator == "nested/two.MP4")
assert restored.id == initial_ids["nested/two.MP4"]
assert restored.presence is FilePresenceState.PRESENT and restored.missing_since_utc is None

with factory() as session:
    assert session.scalar(select(func.count()).select_from(CatalogueItemRecord)) == 0
    assert session.scalar(select(func.count()).select_from(PlayableRenditionRecord)) == 0
    assert session.scalar(select(func.count()).select_from(MediaItemRecord)) == 0
elapsed = monotonic() - started
print(
    "task33 elapsed_seconds=",
    elapsed,
    "batch_size=",
    settings.scan_persistence_batch_size,
    "progress_threshold=",
    settings.scan_progress_update_threshold,
    "worker_concurrency=",
    settings.scan_worker_concurrency,
)
engine.dispose()
PY

# Focused tests above prove failed/interrupted scans, cancellation after a committed batch,
# one-active-scan DB/application enforcement, abandoned-run recovery and repeated Phase 2 runtime
# reads from the same disposable DB. The real fixture proves Linux traversal/symlink behavior.
test ! -e "$ffprobe_marker"
test "$(git status --porcelain)" = ""

# Remove every disposable source, database, fake executable, environment and worktree.
sudo -u nostalgia rm -r -- "$validation_root"
sudo -u nostalgia rm -- "$hardware_db"
rm -r -- "$migration_root" "$fake_bin"
cd -
git worktree remove --force /tmp/nostalgiabox-task33
```

Record Debian/Python versions; full and focused totals/skips; Ruff/mypy; every Alembic revision;
real fixture IDs/counters/issues/times; cancellation/recovery/mutual-exclusion/runtime results;
elapsed time and provisional settings; the absent ffprobe marker; clean Git status; and complete
cleanup. Do not convert Task 3.3 to `PASS` until this procedure is physically completed.

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
