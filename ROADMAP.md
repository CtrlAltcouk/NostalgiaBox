# NostalgiaBox Roadmap

This roadmap gives the high-level delivery order. Detailed tasks, tests, documentation outputs and exit criteria are maintained in [`docs/01_Project/DETAILED_DELIVERY_PLAN.md`](docs/01_Project/DETAILED_DELIVERY_PLAN.md).

Dates are deliberately omitted until the architecture and hardware validation are complete.

## Phase 0 — Product and project foundation

Define the product, requirements, delivery controls, risks and architecture decisions.

**Exit:** version-one scope and the implementation process are agreed.

## Phase 1 — Hardware validation and appliance base

Validate the Dell OptiPlex 7050, select the operating system, prove hardware-accelerated playback and establish hidden, reliable appliance startup.

**Exit:** the hardware and base installation are repeatable and stable.

## Phase 2 — Core architecture and proof of concept

Select technologies and prove one continuously advancing real-time channel that tunes at the correct programme offset.

**Exit:** the highest-risk product behaviour is demonstrated on the reference hardware.

## Phase 3 — Media library and catalogue

Support internal, USB and SMB/NAS sources, scanning, matching, metadata and manual corrections. Plex and Jellyfin follow through adapters rather than becoming required dependencies.

**Exit:** the internal catalogue is reliable and independent of external media servers.

## Phase 4 — Channel engine and scheduling

Create editable channels, scheduling rules, stable future timelines, seasonal activation and deterministic recovery behaviour.

**Exit:** multiple channels continuously produce valid now/next schedules.

## Phase 5 — Playback coordination and television interface

Implement channel tuning, pause/resume, channel changes, startup sequence, channel banner, remote navigation and user-friendly recovery.

**Exit:** core viewing works from the sofa without exposing Linux.

## Phase 6 — Electronic programme guide and reminders

Build an original NostalgiaBox guide inspired by familiar classic guide behaviour, with programme information, current-time navigation and reminders.

**Exit:** users can discover and tune programmes entirely by remote.

## Phase 7 — Administration web interface

Provide setup, media management, channel editing, schedule preview, settings, diagnostics, backup and maintenance through a protected local web interface.

**Exit:** routine administration no longer requires direct Linux access.

## Phase 8 — Reliability, installation and updates

Add supervision, migrations, backup/restore, repeatable provisioning, upgrades, rollback, health reporting and long-duration testing.

**Exit:** a clean reference machine can be converted and maintained using documented procedures.

## Phase 9 — Enclosure and physical integration

Measure and model the hardware, preserve Dell cooling, create a serviceable custom enclosure and document manufacture and assembly.

**Exit:** the physical appliance is safe, reproducible and thermally validated.

## Phase 10 — Optional continuity and future enhancements

After the core platform is stable, consider adverts, advanced idents, seasonal themes, additional guide themes, rewind, channel packs, profiles and a physical channel display.

Adverts are explicitly deferred and do not block version 1.0.

## Version 1.0 outcome

A user can add their own media, create real-time scheduled channels, watch and navigate by remote, use an original programme guide, pause playback, administer the device through a web UI, restart without seeing Linux and recover from routine failures using documented appliance procedures.
