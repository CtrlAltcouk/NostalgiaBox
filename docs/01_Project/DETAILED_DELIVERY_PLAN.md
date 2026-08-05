# NostalgiaBox Detailed Delivery Plan

This plan turns the product vision into controlled delivery phases. Each phase defines its purpose, dependencies, work packages, documentation outputs, validation activities and exit criteria.

No phase is considered complete because code exists. It is complete only when its acceptance criteria are demonstrated and its documentation is updated.

---

## Phase 0 — Product and project foundation

### Purpose

Create a single source of truth before implementation begins.

### Work packages

1. **Product definition**
   - Confirm the one-sentence product statement.
   - Record intended users and emotional goals.
   - Define version-one scope and explicit non-goals.
   - Record the principle that the product must feel like a television rather than a computer.

2. **Repository governance**
   - Establish repository folders and naming conventions.
   - Define branch and pull-request workflow.
   - Add issue and pull-request templates.
   - Add contribution, security and licensing decisions before public release.

3. **Requirements management**
   - Maintain the product requirements document.
   - Assign requirement identifiers when implementation begins.
   - Link implementation issues and tests back to requirements.

4. **Risk management**
   - Maintain technical, legal, usability and hardware risks.
   - Record mitigations and owners.

### Documentation outputs

- Product requirements
- Vision and scope
- Roadmap
- Detailed delivery plan
- Architecture decision records
- Initial risk register

### Validation

- Review all documents for contradictions.
- Confirm that adverts and rewind are not blocking version-one work.
- Confirm that the core channel behaviour is real-time.

### Exit criteria

- The product direction is approved.
- Version-one boundaries are clear.
- All major unresolved technical choices are listed.
- Implementation work can be traced to documented goals.

---

## Phase 1 — Hardware validation and appliance base

### Purpose

Turn the Dell OptiPlex 7050 Micro into a reliable, measurable development platform.

### Dependencies

- Delivered hardware
- Compatible power supply
- Display and audio equipment
- Keyboard for setup
- Representative test media

### Work packages

1. **Physical inspection**
   - Record model, CPU, RAM, storage and firmware revision.
   - Photograph motherboard, cooling, connectors and chassis.
   - Confirm that the additional RAM is compatible.
   - Inspect fan, heatsink, thermal condition and cables.

2. **Hardware diagnostics**
   - Run memory tests.
   - Check SSD health and capacity.
   - Stress-test CPU and video playback.
   - Verify HDMI/DisplayPort audio, USB, Ethernet and Wi-Fi where fitted.
   - Measure idle and playback temperatures.

3. **Operating-system investigation**
   - Compare suitable lightweight Linux bases.
   - Test boot time, driver support, hardware decoding and recovery behaviour.
   - Decide whether a minimal distribution, immutable image or conventional installation best supports the appliance goal.

4. **Appliance startup and shutdown**
   - Configure automatic application startup.
   - Remove visible login and desktop surfaces.
   - Define safe power-button behaviour.
   - Define restart after power loss.
   - Create a maintenance escape route for administrators.

5. **Baseline performance**
   - Test common 720p, 1080p and selected 4K files.
   - Test H.264, H.265/HEVC and common audio formats.
   - Record unsupported or unreliable formats.

### Documentation outputs

- Hardware inventory
- Validation results
- Thermal and power observations
- Base-OS comparison
- Repeatable installation notes
- Known hardware limitations

### Tests

- Cold boot and warm reboot
- 30-minute and multi-hour playback
- Power-loss recovery
- Audio after reboot
- Remote/keyboard detection
- Network reconnection

### Exit criteria

- Hardware passes diagnostics.
- The operating-system direction is approved through an ADR.
- Full-screen playback is stable.
- The application can start without exposing Linux.
- A clean installation can be repeated from documentation.

---

## Phase 2 — Core architecture and technical proof of concept

### Purpose

Prove the hardest product assumption: a channel can behave like a continuous real-time television broadcast.

### Work packages

1. **System architecture**
   - Define boundaries between TV UI, web UI, application service, scheduler, catalogue, database and playback engine.
   - Define local APIs and event flow.
   - Decide process supervision and failure recovery.

2. **Technology selection**
   - Select playback engine.
   - Select backend language/framework.
   - Select TV frontend technology.
   - Select web frontend technology.
   - Select database.
   - Record each major decision in an ADR.

3. **Minimal media model**
   - Define media item, episode, movie, channel, schedule entry and playback session.
   - Create a tiny seeded test catalogue using legal test media.

4. **Real-time channel calculation**
   - Define a deterministic channel timeline.
   - Calculate the programme active at the current time.
   - Calculate the exact seek position within that programme.
   - Handle gaps, overlaps and invalid entries.

5. **Playback proof**
   - Display one channel full screen.
   - Tune into the correct real-time offset.
   - Restart the application and return to the correct live position.
   - Change away and back without restarting the programme.

6. **Basic input**
   - Support keyboard commands for channel change, guide placeholder, pause and back.
   - Capture USB remote key events for investigation.

### Documentation outputs

- System context and container diagrams
- API boundary notes
- Initial domain model
- Real-time timeline algorithm
- Technology ADRs
- Proof-of-concept test report

### Tests

- Tune before, during and after a programme boundary.
- Restart at different offsets.
- Test files with different durations.
- Test missing and corrupt files.
- Verify clock and timezone handling.
- Verify daylight-saving transition strategy.

### Exit criteria

- One real-time channel works deterministically.
- Playback begins at the correct position.
- Restart and retune behaviour is proven.
- Chosen technologies satisfy the hardware and appliance constraints.
- No core assumption remains untested.

---

## Phase 3 — Media library and catalogue

### Purpose

Create a reliable internal catalogue independent of Plex or Jellyfin.

### Work packages

1. **Source management**
   - Add internal-folder sources.
   - Add removable USB sources.
   - Add SMB/NAS sources.
   - Store credentials securely.
   - Detect unavailable and reconnected sources.

2. **Scanning**
   - Discover supported files.
   - Extract technical metadata and duration.
   - Avoid duplicate catalogue entries.
   - Detect additions, changes and removals.
   - Support full and incremental scans.

3. **Organisation and matching**
   - Identify movies, series, seasons and episodes.
   - Permit manual corrections through the web UI.
   - Preserve user edits across rescans.

4. **Metadata and artwork**
   - Define metadata-provider abstraction.
   - Cache artwork locally.
   - Provide fallback artwork and titles.
   - Respect provider licences and rate limits.

5. **External integrations**
   - Design Plex and Jellyfin adapters after local/SMB sources are stable.
   - Map external identifiers to the internal catalogue.
   - Do not make either service mandatory.

6. **Storage management**
   - Show free space and source health.
   - Define cache limits and cleanup.
   - Exclude user media and credentials from Git.

### Documentation outputs

- Media-source model
- Supported formats
- Naming and matching rules
- Scan lifecycle
- Credential-storage design
- Metadata-provider design

### Tests

- Add, remove, rename and replace files.
- Disconnect a NAS during scanning and playback.
- Reconnect removable storage.
- Scan duplicate files and duplicate names.
- Process large libraries without blocking playback.
- Preserve manual corrections.

### Exit criteria

- Local and SMB media can be catalogued reliably.
- Scans are repeatable and recover from interruption.
- Users can correct metadata through the web interface.
- Playback references catalogue identifiers rather than raw UI-selected paths.

---

## Phase 4 — Channel engine and scheduling

### Purpose

Generate stable, editable, real-time television channels from catalogue content.

### Work packages

1. **Channel definitions**
   - Number, name, logo, enabled state and ordering.
   - Startup and seasonal activation settings.
   - Content pools and scheduling rules.

2. **Scheduling model**
   - Define programmes, blocks, rules and exclusions.
   - Support sequential episodes and shuffled pools.
   - Avoid immediate repetition.
   - Support day-of-week and time-of-day rules.
   - Define filler behaviour when no normal item fits.

3. **Timeline generation**
   - Generate schedules ahead for an agreed horizon.
   - Keep already published schedule entries stable.
   - Extend the future timeline without rewriting history.
   - Store provenance explaining why each item was selected.

4. **Real-time resolution**
   - Resolve current and next entries efficiently.
   - Calculate seek offsets.
   - Handle clock changes and timezone configuration.

5. **Channel editing through web UI**
   - Create from a template.
   - Edit and preview rules.
   - Reorder and renumber.
   - Enable, disable and schedule seasonal visibility.
   - Warn about empty or invalid channels.

6. **Recovery and consistency**
   - Handle removed media already present in a schedule.
   - Rebuild future schedules safely.
   - Protect against duplicate or overlapping entries.

### Documentation outputs

- Channel schema
- Scheduling-rule specification
- Timeline generation algorithm
- Determinism and randomisation policy
- Seasonal activation design
- Schedule repair procedures

### Tests

- Generate multiple days for multiple channels.
- Re-run generation and confirm protected entries do not change.
- Test empty content pools.
- Test programmes crossing midnight.
- Test seasonal channel activation.
- Remove scheduled media and verify fallback.
- Test daylight-saving transitions.

### Exit criteria

- Users can create and edit multiple channels.
- Each channel produces a valid future timeline.
- Current/next resolution is reliable.
- Schedules remain stable where promised.
- Invalid rules are visible and recoverable.

---

## Phase 5 — Playback coordination and television interface

### Purpose

Deliver the core sofa experience without requiring a keyboard or mouse.

### Work packages

1. **Playback coordinator**
   - Tune to a channel and correct offset.
   - Change channels cleanly.
   - Pause and resume.
   - Select audio and subtitles.
   - Recover from playback-process failure.
   - Fall back when media is unavailable.

2. **Startup flow**
   - Show NostalgiaBox logo.
   - Apply optional CRT static.
   - Show channel ident when configured.
   - Display channel-information banner.
   - Start Channel 001 by default or the saved channel when configured.

3. **Channel banner**
   - Channel number and name.
   - Current programme.
   - Start/end or remaining time.
   - Progress indicator.
   - Optional channel watermark.

4. **Remote navigation shell**
   - Channel up/down.
   - Direct number entry where available.
   - Guide, info, back and play/pause.
   - Focus management that never loses the selected control.
   - Consistent key-repeat behaviour.

5. **Error presentation**
   - Friendly messages rather than technical exceptions.
   - Automatic retry where safe.
   - A hidden diagnostic code that can be looked up in the web UI.

6. **Accessibility and child usability**
   - Readable text at television distance.
   - Large focus targets.
   - Minimal required steps.
   - No destructive actions without confirmation or PIN.

### Documentation outputs

- TV navigation map
- Remote key map
- Startup-state machine
- Playback-state machine
- Error and fallback catalogue
- UI spacing and readability rules

### Tests

- Operate all core functions using only the target remote.
- Test rapid channel changes.
- Pause across a programme boundary and define expected behaviour.
- Recover from decoder crash.
- Test subtitle and audio selection.
- Test overscan and common 1080p television layouts.

### Exit criteria

- A normal viewing session requires only the remote.
- Linux is not visible.
- Channel switching and pause are reliable.
- Failures produce user-friendly recovery behaviour.

---

## Phase 6 — Electronic programme guide and reminders

### Purpose

Provide a familiar but original programme-discovery experience.

### Work packages

1. **NostalgiaBox visual language**
   - Define typography, spacing, motion, colours and focus states.
   - Take inspiration from classic guides without copying protected branding or layouts.

2. **Guide grid**
   - Channel column.
   - Time axis.
   - Current-time marker.
   - Programme cells sized by duration.
   - Smooth horizontal and vertical navigation.

3. **Programme information**
   - Title, synopsis, episode data, timing and artwork.
   - Now/next information.

4. **Reminders**
   - Set and cancel reminders.
   - Display notification before a programme begins.
   - Offer one-action tuning.
   - Define behaviour while playback is paused or settings are open.

5. **Theme architecture**
   - Keep presentation tokens separate from guide logic.
   - Prepare for future selectable guide themes.

6. **Performance**
   - Load only the visible schedule window.
   - Cache images.
   - Maintain remote responsiveness while the schedule updates.

### Documentation outputs

- EPG interaction specification
- Originality and brand-separation notes
- Reminder lifecycle
- Theme-token specification
- Performance budgets

### Tests

- Guides with few and many channels.
- Short and multi-hour programmes.
- Programmes spanning the visible window.
- Rapid navigation.
- Missing metadata and artwork.
- Reminder timing around sleep/restart.

### Exit criteria

- The guide is usable entirely by remote.
- Current and upcoming schedules are accurate.
- Reminder behaviour is dependable.
- The design is recognisably NostalgiaBox rather than a copy of another service.

---

## Phase 7 — Administration web interface

### Purpose

Move complex management away from the television while keeping it accessible on the local network.

### Work packages

1. **Setup and status dashboard**
   - Device status, version, storage, sources and channel health.
   - First-run setup workflow.

2. **Media management**
   - Add and test sources.
   - Start and monitor scans.
   - Correct matches and artwork.

3. **Channel management**
   - Create from templates.
   - Edit content pools and schedule rules.
   - Preview schedule output.
   - Manage logos, colours, idents and activation windows.

4. **System settings**
   - Startup channel behaviour.
   - CRT effect toggle.
   - Timezone, language and display settings.
   - Remote mapping.
   - PIN management.

5. **Diagnostics and maintenance**
   - Health status and logs.
   - Backup and restore.
   - Restart services or device.
   - Safe update workflow.

6. **Security**
   - Local authentication or setup token.
   - CSRF and session protection.
   - Secure credential storage.
   - Restrict access to the local network by default.

### Documentation outputs

- Web UI sitemap
- API contract
- Authentication model
- Backup contents and restore process
- First-run setup specification

### Tests

- Complete setup from a phone and desktop browser.
- Invalid credentials and inaccessible shares.
- Concurrent TV playback and library scans.
- Backup and restore to a clean installation.
- PIN-protected settings.

### Exit criteria

- All advanced version-one configuration is possible through the web UI.
- Routine administration does not require Linux access.
- Security controls are documented and tested.

---

## Phase 8 — Reliability, installation and updates

### Purpose

Convert a working prototype into a maintainable appliance.

### Work packages

1. **Service supervision**
   - Automatic restart of failed components.
   - Health checks and dependency ordering.
   - Controlled degraded modes.

2. **Data protection**
   - Database migrations.
   - Automatic backups before upgrades.
   - Restore verification.
   - Recovery from interrupted writes.

3. **Installation**
   - Repeatable provisioning from a clean machine.
   - Hardware checks.
   - Initial configuration wizard.
   - Version reporting.

4. **Updates**
   - Signed or verified release packages.
   - Staged upgrade process.
   - Rollback strategy.
   - Clear compatibility and migration notes.

5. **Observability**
   - Structured logs.
   - User-friendly health status.
   - Exportable support bundle with secrets removed.

6. **Long-duration validation**
   - Multi-day playback.
   - Schedule extension.
   - Network interruptions.
   - Repeated suspend/restart/power cycles if supported.

### Documentation outputs

- Installation guide
- Upgrade and rollback guide
- Backup and restore guide
- Troubleshooting guide
- Release checklist
- Support-bundle privacy specification

### Exit criteria

- A clean OptiPlex can be converted by following the guide.
- Updates preserve configuration and schedules.
- Common failures recover automatically.
- Long-running tests meet agreed reliability thresholds.

---

## Phase 9 — Enclosure and physical integration

### Purpose

Create the final physical appliance without compromising serviceability or cooling.

### Work packages

1. **Measurement and reference model**
   - Record motherboard outline, mounting holes and component heights.
   - Record rear I/O and power-button geometry.
   - Record fan intake and exhaust requirements.

2. **Mechanical architecture**
   - Separate motherboard tray, outer shell, front panel and cover.
   - Preserve access to RAM, storage and cooling.
   - Provide strain relief and stable rear I/O support.

3. **Thermal design**
   - Preserve the Dell airflow path.
   - Avoid recirculation.
   - Validate printed-material temperature limits.
   - Compare temperatures against the original chassis.

4. **Front panel**
   - Define physical power and navigation controls.
   - Decide whether a channel display is version one or future.
   - Hide or integrate modern ports appropriately.

5. **Prototype iterations**
   - Fit-check print.
   - Functional prototype.
   - Thermal prototype.
   - Final cosmetic revision.

6. **Manufacturing documentation**
   - Source CAD and neutral STEP files.
   - Printable STL/3MF files.
   - Print orientation and settings.
   - Fastener and assembly list.

### Documentation outputs

- Dimensioned hardware model
- Thermal requirements
- Mechanical design decisions
- Bill of materials
- Print and assembly guide
- Revision history

### Tests

- Fit and connector alignment.
- Cable strain and service access.
- Multi-hour thermal test.
- Button endurance.
- Drop/handling assessment appropriate to a home appliance.

### Exit criteria

- The enclosure is safe, serviceable and thermally acceptable.
- Assembly is reproducible.
- CAD and printing documentation match the released revision.

---

## Phase 10 — Optional continuity, adverts and future enhancements

### Purpose

Add atmosphere only after the core experience is reliable.

### Candidate work packages

- Channel idents and bumpers
- “Coming up next” clips
- Channel- and season-specific adverts
- Seasonal guide themes and channels
- Additional programme-guide themes
- Rewind/time-shift buffer
- Plex and Jellyfin enhancements
- Channel-pack import/export
- Multiple household profiles
- Physical channel-number display

Each candidate requires a separate design and prioritisation exercise. None may weaken startup speed, channel reliability or ease of use.

### Exit criteria

Defined separately for each approved feature. Optional features do not block version 1.0 unless explicitly promoted into scope through an updated product decision.

---

## Cross-phase controls

Every implementation phase must include:

- an approved design or ADR for significant decisions;
- implementation issues with acceptance criteria;
- automated tests where practical;
- manual appliance/remote validation;
- migration or rollback consideration;
- updated user and developer documentation;
- confirmation that no copyrighted user media or secrets have entered the repository.

## Definition of done for version 1.0

Version 1.0 is ready only when:

- real-time channels are stable;
- local and SMB media sources work;
- schedules can be created and edited through the web UI;
- playback, channel changing, pause and the EPG work by remote;
- reminders work;
- Linux remains hidden during normal use;
- installation, update, backup and recovery procedures are documented and tested;
- the reference hardware passes long-duration testing;
- the enclosure either meets release criteria or is explicitly separated as a later hardware release.
