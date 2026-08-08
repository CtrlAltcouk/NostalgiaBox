# ADR-007 — Use Python 3.13 and FastAPI for the core backend

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

Phase 2 needs a maintainable core runtime that can express deterministic scheduling rules, control MPV, own the database, expose a future administration API and remain straightforward to test on the Debian 13 reference appliance.

The computationally expensive media work is performed by MPV/FFmpeg and the Intel GPU, not by the application language. The core primarily performs time calculations, database operations, orchestration, input translation and API work.

Candidates included Python, Node.js/TypeScript, Rust and C++.

## Decision

Use Python 3.13 as the primary core/backend language.

Use FastAPI for the local HTTP/API boundary and Pydantic for validation/serialization at external boundaries where appropriate.

Keep domain and application logic independent of FastAPI request/response objects so the core remains testable without HTTP.

## Rationale

- Debian 13 provides a current Python 3 runtime.
- Python is well suited to deterministic domain logic, orchestration and hardware/service integration.
- Mature libraries exist for SQLite/SQLAlchemy, MPV IPC, evdev/input work, testing and system integration.
- FastAPI gives a clean path to the Phase 3 administration WebUI without forcing the WebUI to own business logic.
- Developer productivity and maintainability are more valuable here than implementing media/rendering code in a systems language.
- Performance-critical decode/rendering remains in MPV/FFmpeg/VA-API.

## Consequences

### Positive

- Fast iteration and strong testability.
- One backend can serve appliance runtime and future WebUI API needs.
- Clear dependency-injection boundaries for clock, database and player adapters.
- Easy to run on the existing Debian appliance.

### Negative

- Python runtime/dependencies must be packaged and versioned carefully.
- Type discipline is not enforced by the language runtime, so typing/linting/tests are important.
- Long-running process design must avoid blocking the API/event loop with slow synchronous work.

## Constraints

- Domain code must not import FastAPI.
- Blocking filesystem/database/player operations must be isolated appropriately.
- Project dependencies must be pinned/managed reproducibly.
- User media and machine-specific runtime configuration remain outside the repository.

## Rejected alternatives

### Node.js/TypeScript core

Viable, especially for web development, but less attractive for Linux input/system integration and would couple more of the core stack to the frontend ecosystem than required.

### Rust

Excellent performance and reliability potential, but the added implementation complexity is not justified for a runtime whose heavy media processing is delegated to MPV.

### C++

Provides maximum low-level control but would substantially increase development and maintenance cost without solving a current requirement.
