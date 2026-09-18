# Task 3.5 — identity reconciliation validation and acceptance evidence

## Scope and status

Local repository-backed work on 2026-09-18, branch `codex/phase-3.5-identity-reconciliation`, base `adee34e20aa84a23271f2ad1ab93942d6107de9b`. Changes are uncommitted. Reference-Dell validation is complete, but Task 3.5 is not accepted, merged, or deployed; Phase 3 remains PARTIAL.

No Task 3.6 work, commit, push, PR, production checkout access, or source-media mutation occurred. Dell validation used only a disposable worktree, database and generated files.

## Current revision semantics

- Durable evidence binds active file ID/revision, source revision, physical observation (source, both locators, presence, size, mtime, device, inode), and requested algorithm/version policy.
- `last_seen_generation` and scan observation timestamps are excluded from durable evidence validity and the physical CAS guard. A generation-only scan advance therefore reuses evidence.
- Generation is scan bookkeeping only: per-run duplicate protection, discovery provenance, and successful-enumeration unseen/missing reconciliation. It is not physical validity evidence.
- Physical observation, source revision/configuration, and policy changes continue to invalidate evidence. In-flight hashing still rejects those changes atomically.

## Regression coverage

- `test_three_completed_rescans_reuse_durable_evidence_without_hashing`: after an initial quick hash, three completed later scans using `identity_inspector=service.inspect` make zero additional gateway calls; the original evidence remains current at generation 4.
- `test_new_generation_reuses_evidence_with_unchanged_cheap_fields_even_in_flight`: quick and full cases advance only `last_seen_generation` from the gateway callback. Each append succeeds and the immediate second inspection is a cache hit: one call total per case.
- Complementary physical stale-read coverage remains size/inode/presence × quick/full. Existing blocker coverage retains locator/device/revision/source-revision/ABA rejection; cache coverage retains physical and policy-version invalidation.

## Test-count reconciliation

| Collection point | Full | Focused Task 3.5 | Reconciliation |
| --- | ---: | ---: | --- |
| Earlier claimed checkpoint | 504 | 86 | Not reproducible from this worktree, backup, or Git history; it is not validation evidence. |
| Before this correction | 496 | 78 | Actual collection of the current uncommitted workspace. |
| Current terminal-lifecycle and ambiguity correction | 504 | 92 | Filters terminal provisional discoveries from every reconciliation predecessor/candidate path and replaces the changed-replacement ambiguity regression with distinct ambiguous contexts A→B; the focused command includes identity, blockers, migration, scan coordinator, and subprocess tests. |

No collected test was removed by this correction. The failed-provisional cases prove unresolved valid recovery, terminal stale/resolved non-resurrection across successor, missing-predecessor, alias, similarity, and replacement paths, terminal audit preservation, and retry safety. The ambiguity regression proves unchanged repeats of context A and context B are independently idempotent, while changed ambiguous context A→B appends distinct immutable Needs Attention evidence and preserves A; it does not rely on a replacement transition. Blocker regressions are located in `test_identity_blockers.py`, lifecycle coverage in `test_identity_migration.py`, and scan/subprocess coverage is included in the focused selector.

## Migration and validation evidence

`20260915_0006_identity_reconciliation.py` remains additive on parent `20260914_0005`; this correction requires no migration change. It retains immutable `identity_discovery_resolutions` (`resolved`/`stale`) and the unique snapshot-keyed identity-decision constraint. Lifecycle tests cover empty/populated upgrades, downgrade/re-upgrade, immutable guards, schema comparison, and foreign-key checking.

Reproduced locally on 2026-09-18 with Python 3.13.15. The focused selector was `tests/integration/test_identity.py tests/integration/test_identity_blockers.py tests/integration/test_identity_migration.py tests/integration/test_scan_coordinator.py tests/unit/probe/test_subprocess_runner.py`.

| Check | Current result |
| --- | --- |
| Full pytest (local) | 504 passed, 1 existing Starlette warning |
| Focused Task 3.5 / scan / migration / subprocess (local) | 92 passed |
| Alembic lifecycle | populated upgrade/downgrade/re-upgrade included in focused result |
| Ruff lint / format / strict mypy / diff check | Clean: Ruff passed; 139 files already formatted; strict mypy checked 132 source files; diff check passed. |

## Reference-Dell validation (2026-09-18)

Validation used a disposable copy under `/tmp`, a disposable Python 3.13 environment and generated temporary files only. `/opt/nostalgiabox`, production databases, media, services, MPV, X, autologin, systemd, boot and network configuration were not touched. The host was `NostalgiabOX`, Debian GNU/Linux 13.6, Linux 6.12.101, ext4-backed system with `/tmp` on tmpfs, Intel Core i5-7500 (4 cores), 15 GiB RAM, Python 3.13.5 and ffprobe 7.1.5.

| Check | Dell result |
| --- | --- |
| Full pytest | 510 passed, 1 existing Starlette warning, 11.93s |
| Focused identity/fingerprint/migration tests | 92 passed, 7.31s |
| Migration/catalogue compatibility tests | 19 passed |
| Alembic lifecycle | Passed within migration coverage |
| Ruff lint / format | Passed; 132 files already formatted |
| Strict mypy | Passed; 132 source files |
| Generated filesystem rename/copy/replacement scenario | 1 passed |
| Reconciliation query-scaling regression | 6 passed |

Generated-files coverage exercised stable-ID rename, copy-as-distinct-identity, duplicate confirmation without media mutation, same-path replacement, swap/cycle, failed-scan provisional recovery, terminal stale/resolved exclusion, ambiguity, and unchanged rescans. The full and focused suites also cover disappearance/change-during-hash, policy invalidation, duplicate membership races and stale-result rejection.

The Dell scaling regression measured the historical-evidence query bound at 10 files: 4 SQL statements; 100 files: 4; and 1,000 files: 5 (two bounded 500-ID history batches). The complete six-case 10/100/1,000 no-history/mixed-history run completed in 2.626 seconds on the Dell. No quadratic query growth or SQLite lock failure was observed. The generated local filesystem test completed in 0.30 seconds.

Fingerprint measurements on generated sparse files were: quick 0.000581s/0.000506s/0.000454s for 1/10/100 MiB; full SHA-256 0.002482s/0.021449s/0.207959s, approximately 384/445/459 MiB/s. The measured provisional policy remains three bounded 64 KiB samples (start/middle/end), confirmation limit 8, and the existing bounded scan executor; no aggressive tuning was introduced.

No severe SQLite contention, stale evidence acceptance, identity corruption, reference retargeting, unsafe media mutation or unbounded hashing was observed. Task 3.5 remains uncommitted and not merged; Phase 3 remains PARTIAL. The focused final Expert review returned APPROVE; commit and PR remain pending explicit follow-up.
