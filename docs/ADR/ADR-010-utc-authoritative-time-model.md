# ADR-010 — Use UTC as the authoritative timeline time model

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

NostalgiaBox channels advance continuously against real time. Incorrect handling of local time, daylight-saving changes or machine timezone would select the wrong programme or seek offset.

The reference appliance is currently used in the United Kingdom, where `Europe/London` alternates between GMT and BST. The product should not embed UK-specific assumptions into its core scheduling logic.

## Decision

Represent and persist authoritative timeline start/end instants in UTC.

Use timezone-aware datetime values only. Naive datetimes are invalid at domain boundaries.

Configured local timezone is used for authoring schedules, displaying human times and interpreting explicitly local configuration. It is not the storage identity of a timeline instant.

Introduce a clock abstraction so runtime logic uses a system clock while automated tests can use a fixed/fake clock.

## Real-time resolution rule

For `now_utc`, an entry is active when:

```text
entry.start_utc <= now_utc < entry.end_utc
```

The live playback offset is:

```text
now_utc - entry.start_utc
```

## Rationale

- Absolute instants remain unambiguous through DST changes.
- Restart, suspend and channel-return behaviour can use the same calculation.
- Automated tests can reproduce exact boundaries.
- Future users are not tied to the reference appliance's local timezone.

## Consequences

### Positive

- One authoritative calculation for live channel position.
- DST complexity is kept at authoring/presentation boundaries rather than inside playback resolution.
- Easier deterministic testing.

### Negative

- Schedule authoring code must explicitly handle ambiguous/non-existent local times.
- All code must consistently use aware datetimes and conversions.

## Constraints

- Do not use `datetime.now()` directly in domain/application scheduling logic; use the injected clock.
- Do not silently attach a local timezone to naive datetimes.
- Persisted timeline records must round-trip without losing absolute instant semantics.
- `Europe/London` DST boundary tests are required during Phase 2.

## Relationship to ADR-003

ADR-003 defines the real-time channel behaviour. This ADR defines the time representation required to implement that behaviour reliably.
