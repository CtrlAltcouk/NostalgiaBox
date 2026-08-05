# ADR-001: Project Name and Product Form

- **Status:** Accepted
- **Date:** 2026-08-03

## Context

The project needs a stable identity and a clear statement of what kind of product is being built. Without this, technical decisions may drift toward a conventional desktop media library or server.

## Decision

The project is named **NostalgiaBox**.

NostalgiaBox will be designed as a standalone television appliance:

- installed on a dedicated computer connected to a television
- operated primarily by remote control
- booting directly into the application
- centred on scheduled channels and channel surfing
- usable without a separate media-server host

## Consequences

### Positive

- Product decisions can be evaluated against a clear appliance experience.
- The interface can prioritise television viewing over library browsing.
- Hardware, enclosure and software can be designed as one product.
- Documentation and repository naming remain consistent.

### Negative

- Supporting ordinary desktop use is not a priority.
- Appliance startup, shutdown and recovery require additional engineering.
- Remote-only navigation raises accessibility and testing requirements.
- The initial release will target a narrower deployment model.

## Alternatives considered

### General desktop media application

Rejected because it would weaken the set-top-box experience and encourage mouse-and-keyboard workflows.

### Service hosted on the existing Proxmox environment

Rejected for the reference build because the owner wants a self-contained box beneath or beside the television.
