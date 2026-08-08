# NostalgiaBox Roadmap

This roadmap gives the high-level delivery order. Detailed tasks, tests, documentation outputs and exit criteria are maintained in [`docs/01_Project/DETAILED_DELIVERY_PLAN.md`](docs/01_Project/DETAILED_DELIVERY_PLAN.md).

Dates are deliberately omitted until the architecture and hardware validation are complete.

## Product delivery strategy

NostalgiaBox will be delivered in two experience layers:

1. **Basic Mode** — the first complete, usable product. It recreates the simple experience demonstrated by the original inspiration: boot directly into television playback, switch between continuously running real-time channels, show a compact channel-information overlay and manage everything through the administration web interface.
2. **Enhanced Guide Mode** — a later feature layer that adds the richer set-top-box experience: a full programme guide, reminders, deeper programme discovery, direct channel selection and additional presentation features.

“Enhanced Guide Mode” is a working name and may change before release. It deliberately avoids using third-party product or service names.

The core engine, catalogue, scheduler, playback system and web administration interface are shared by both modes. Enhanced Guide Mode must extend the core rather than replace or fork it.

## Phase 0 — Product and project foundation

Define the product, requirements, delivery controls, risks and architecture decisions.

**Exit:** Basic Mode scope, later enhancement boundaries and the implementation process are agreed.

## Phase 1 — Hardware validation and appliance base

**Status: Complete — 2026-08-08.** The reference Dell platform now boots into a hidden appliance playback session with working display, audio, hardware-accelerated playback, remote input and suspend/resume behaviour. The current Nordic USB remote can initiate standby but cannot wake the machine from S3; a wake-capable replacement receiver is required for the final sofa-only power experience and is documented in [`docs/03_Hardware/REMOTE_CONTROL.md`](docs/03_Hardware/REMOTE_CONTROL.md).

Validate the Dell OptiPlex 7050, select the operating system, prove hardware-accelerated playback and establish hidden, reliable appliance startup.

**Exit:** the hardware and base installation are repeatable and stable.

## Phase 2 — Core architecture and proof of concept

**Status: In progress — 2026-08-08.** Architecture and technology selection are being completed before the first Codex implementation task. The proof target is one deterministic real-time channel that resolves the correct media item and wall-clock playback offset after tune, restart and resume.

Select technologies and prove one continuously advancing real-time channel that tunes at the correct programme offset.

**Exit:** the highest-risk real-time playback behaviour is demonstrated on the reference hardware.

## Phase 3 — Basic media library and administration web UI

Support internal storage and SMB/NAS sources first, scan and catalogue media, provide manual corrections, and expose essential setup through the web UI. USB, Plex and Jellyfin follow after the local catalogue is stable.

**Exit:** media can be added, scanned, corrected and managed without using the Linux desktop or terminal.

## Phase 4 — Basic real-time channel engine

Create editable channels, simple content pools, deterministic real-time timelines and safe fallback behaviour. Advanced scheduling rules and seasonal activation are deferred.

**Exit:** multiple basic channels run continuously and resolve the correct current programme and playback offset.

## Phase 5 — Basic Mode television experience

Implement appliance startup, full-screen playback, channel up/down, pause/resume, a compact channel-information banner, optional CRT transition, remote input and user-friendly recovery.

A full programme-grid interface is not required in this phase.

**Exit:** NostalgiaBox works like the original simple concept from power-on to everyday channel surfing using only the remote.

## Phase 6 — Basic Mode hardening and first usable release

Add service supervision, backup and restore, repeatable installation, update preparation, diagnostics and long-duration testing.

**Exit:** Basic Mode is stable, documented and suitable for regular household use.

## Phase 7 — Enhanced Guide Mode foundation

Extend the proven core with direct number entry, richer channel selection, now/next browsing, programme-detail views and theme architecture.

**Exit:** richer navigation works without disrupting Basic Mode.

## Phase 8 — Full electronic programme guide and reminders

Build an original NostalgiaBox guide inspired by familiar classic set-top-box behaviour, including timeline navigation, programme discovery and reminders.

**Exit:** users can browse future schedules and tune programmes entirely by remote.

## Phase 9 — Advanced channels and presentation

Add advanced scheduling rules, channel templates, seasonal activation, richer idents, selectable guide themes and other optional channel features.

**Exit:** advanced features remain optional and the simple Basic Mode experience stays intact.

## Phase 10 — Enclosure and physical integration

Measure and model the hardware, preserve Dell cooling, create a serviceable custom enclosure and document manufacture and assembly.

**Exit:** the physical appliance is safe, reproducible and thermally validated.

## Phase 11 — Optional continuity and future enhancements

After the core and Enhanced Guide Mode are stable, consider adverts, promotions, rewind, profiles, community channel packs, additional integrations and a physical channel display.

Adverts remain explicitly deferred and do not block Basic Mode or the first release.

## Basic Mode release outcome

A user can add their own local or network media through the web UI, create simple real-time channels, switch between them by remote, pause playback, view a compact channel-information overlay, restart without seeing Linux and recover from routine failures.

## Enhanced Guide Mode release outcome

A user can optionally enable a richer set-top-box experience with channel selection, a full original programme guide, reminders, programme discovery and advanced channel features, while retaining the same core engine and administration web UI.
