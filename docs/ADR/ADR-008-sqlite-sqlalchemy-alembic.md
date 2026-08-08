# ADR-008 — Use SQLite with SQLAlchemy 2 and Alembic

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

NostalgiaBox is a single-appliance application. It needs reliable persistence for media metadata, channel definitions, generated timelines, settings and later administration state, but it does not need the operational overhead of a separate database server.

The database must be easy to back up, migrate and recover on a household appliance.

## Decision

Use SQLite as the embedded relational database.

Use SQLAlchemy 2 for persistence mappings/repositories and Alembic for schema migrations from the first implemented schema.

The NostalgiaBox core backend owns database writes. Frontends communicate through the core/API rather than opening the SQLite file directly.

Production database location is expected to be:

```text
/var/lib/nostalgiabox/nostalgiabox.db
```

## Rationale

- No separate database daemon is required.
- SQLite is mature, transactional and appropriate for a single-device appliance.
- Backups can be designed around a small number of local persistent files.
- SQLAlchemy keeps ORM/persistence details out of domain code.
- Alembic prevents later schema evolution from becoming an ad-hoc migration problem.
- The expected catalogue/timeline scale is modest relative to SQLite capability.

## Consequences

### Positive

- Low runtime and operational overhead.
- Simple installation and recovery.
- Strong fit for local-first operation.
- Easy test databases and fixtures.

### Negative

- Multi-process write concurrency must be controlled.
- Network-filesystem hosting of the live database is not supported as a default design.
- Future very high write concurrency would require reassessment.

## Database ownership rule

Only the core backend/repository layer may make authoritative persistence changes.

The WebUI, TV UI and input adapters must not write the SQLite database directly.

## Journal-mode policy

Do not make WAL mode an unreviewed default during Phase 2. Start from SQLite's safe/default behaviour and benchmark/change journaling only when there is a documented concurrency or performance requirement.

## Rejected alternatives

### PostgreSQL/MySQL/MariaDB

Rejected for the reference appliance because a server database adds installation, supervision, backup and recovery complexity without a demonstrated need.

### Raw sqlite3 calls throughout the application

Rejected because persistence details would leak into domain/application logic and make migrations/testing harder to maintain.

### JSON/YAML as the primary persistent store

Rejected because channels, media, timelines and migrations are relational enough that a proper transactional database is a better long-term foundation.
