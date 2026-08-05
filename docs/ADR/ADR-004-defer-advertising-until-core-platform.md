# ADR-004 — Defer advertising and advanced continuity until the core platform is complete

- **Status:** Accepted
- **Date:** 2026-08-05

## Context

Retro adverts, idents, bumpers and promotions can strengthen the nostalgic atmosphere. They also add scheduling complexity, media classification, legal considerations, break placement rules and additional failure cases.

The core product still needs to prove media scanning, real-time channels, playback, remote navigation, the programme guide and the administration web interface.

The product owner rated adverts as low priority for the initial experience and requested that the main television functions be completed first.

## Decision

Advertising and advanced continuity features will not be part of the critical path for the first working platform.

Core implementation will proceed in this order:

1. reliable appliance base;
2. real-time channel proof of concept;
3. media catalogue;
4. scheduling and channel engine;
5. playback and television interface;
6. programme guide and reminders;
7. administration web interface;
8. reliability, installation and updates.

Only after these areas are stable will the project implement optional adverts and advanced continuity.

Simple channel idents may be used earlier where they are required to validate the startup experience, but they must not expand into a complete advert-break system during core development.

## Deferred capabilities

- Channel-specific advert pools
- Seasonal advert pools
- Configurable advert-break placement
- Coming-up-next promotions
- Complex ident rotation
- Sponsorship or continuity blocks
- Advert reporting or history

Weather inserts are not planned.

## Consequences

### Positive

- The hardest and most valuable product behaviours are delivered first.
- Scheduling and playback can be stabilised without advert-break edge cases.
- The first usable release is reached sooner.
- Legal and distribution questions around historic adverts do not block development.

### Negative

- Early prototypes may feel less atmospheric.
- Scheduler interfaces must avoid assumptions that make later continuity insertion difficult.
- A small amount of future extension work may be required.

## Architectural requirement

Although advert insertion is deferred, the scheduling model should support future non-programme timeline entries without a database redesign. Generic concepts such as `schedule item`, `content type` or `continuity item` should be considered during architecture design.

This requirement does not authorise implementing the full feature early; it only prevents an avoidable dead end.
