# NostalgiaBox Detailed Delivery Plan

This plan turns the product vision into controlled delivery phases. Each phase defines its purpose, dependencies, work packages, documentation outputs, validation activities and exit criteria.

No phase is complete merely because code exists. A phase is complete only when its acceptance criteria are demonstrated and its documentation is updated.

## Delivery strategy

NostalgiaBox will be built in two layers:

- **Basic Mode** is the first complete product. It prioritises the simple experience demonstrated by the original YouTube inspiration: boot into playback, change continuously running channels, show a compact information overlay and manage the appliance through a web interface.
- **Enhanced Guide Mode** is a later optional layer. It adds a richer set-top-box experience such as channel-selection screens, a full guide, reminders and advanced channel features.

Both modes share one catalogue, one real-time channel engine, one playback coordinator, one database and one administration web interface. Enhanced Guide Mode must extend the proven core rather than fork it.

---

## Phase 0 — Product and project foundation

### Purpose

Create a single source of truth and prevent advanced features from delaying a usable core product.

### Work packages

1. Confirm the product statement, audience and emotional goals.
2. Define Basic Mode and Enhanced Guide Mode boundaries.
3. Record explicit non-goals for the first release.
4. Establish repository, branch, review and documentation rules.
5. Maintain risks, ADRs and open decisions.
6. Ensure every future implementation task traces to a requirement and acceptance test.

### Documentation outputs

- Product requirements
- Roadmap
- Detailed delivery plan
- Architecture Decision Records
- Risk register
- Documentation index

### Validation

- Check all documents for conflicting scope.
- Confirm that a full EPG, reminders, advanced channel selection and adverts are not Basic Mode blockers.
- Confirm that the administration web UI remains part of the early core.

### Exit criteria

- Basic Mode scope is approved.
- Enhanced Guide Mode is clearly separated but architecturally supported.
- Major unknowns are documented.
- Implementation can begin without relying on undocumented assumptions.

---

## Phase 1 — Hardware validation and appliance base

### Purpose

Turn the Dell OptiPlex 7050 Micro into a reliable development and deployment platform.

### Work packages

1. Record CPU, RAM, storage, firmware, ports and network hardware.
2. Fit and test the additional memory.
3. Check SSD health, fan, heatsink, temperatures and power supply.
4. Test display output, audio, USB, Ethernet and Wi-Fi where fitted.
5. Compare suitable lightweight Linux bases.
6. Test hardware-accelerated H.264 and H.265 playback.
7. Configure automatic startup, hidden Linux surfaces and safe shutdown.
8. Define administrator maintenance access that is invisible during normal use.
9. Record cold-boot, reboot and recovery timings.

### Documentation outputs

- Delivered hardware inventory
- Diagnostic results
- Thermal and playback observations
- Base operating-system comparison
- Repeatable installation notes
- Known hardware limitations

### Tests

- Memory test
- SSD health test
- 720p and 1080p playback
- Representative 4K playback for capability information
- Cold boot and warm reboot
- Multi-hour playback
- Audio after reboot
- Network reconnection
- Power-loss recovery

### Exit criteria

- Hardware passes diagnostics.
- Base OS is selected through an ADR.
- Full-screen playback is stable.
- Linux can be hidden during normal startup.
- Installation can be repeated from documentation.

---

## Phase 2 — Core architecture and one-channel proof

### Purpose

Prove the hardest assumption before building product features: a channel can run continuously against real time and tune at the correct offset.

### Work packages

1. Define boundaries between backend service, TV UI, web UI, catalogue, scheduler, database and playback engine.
2. Select backend, frontend, database and playback technologies.
3. Define the minimum domain model: media item, channel, timeline entry and playback session.
4. Seed legal test media.
5. Build one deterministic channel timeline.
6. Resolve the current programme from system time.
7. Calculate the exact seek position.
8. Start playback full screen at that offset.
9. Restart and return to the correct current position.
10. Capture keyboard and USB-remote input for basic commands.

### Documentation outputs

- System context and component diagrams
- Initial domain model
- Real-time timeline algorithm
- Technology ADRs
- Process-supervision approach
- Proof-of-concept test report

### Tests

- Tune before, during and after programme boundaries.
- Restart at multiple offsets.
- Test different file durations.
- Test missing and corrupt files.
- Test timezone and daylight-saving assumptions.
- Test playback-process failure.

### Exit criteria

- One real-time channel works deterministically.
- Playback begins at the correct position.
- Restart behaviour is correct.
- Selected technologies work on the reference hardware.
- No core real-time assumption remains unproven.

---

## Phase 3 — Basic media catalogue and administration web UI

### Purpose

Make media manageable without exposing Linux or requiring Plex or Jellyfin.

### Work packages

#### 3.1 Catalogue foundation

- Add internal-folder media sources.
- Add SMB/NAS sources.
- Discover supported files.
- Extract duration and technical metadata.
- Detect additions, changes, removals and duplicates.
- Support full and incremental scans.
- Preserve stable catalogue identifiers.

#### 3.2 Basic matching

- Identify movies, series, seasons and episodes where possible.
- Provide sensible fallback titles.
- Allow manual corrections.
- Preserve manual corrections across rescans.
- Cache basic artwork without making artwork a playback dependency.

#### 3.3 Web UI foundation

- Provide first-run setup.
- Add, edit, test and remove media sources.
- Start scans and show progress.
- Show source availability and scan errors.
- Review and correct media matches.
- Show storage and appliance health.

#### 3.4 Security and resilience

- Restrict administration to the local network by default.
- Add setup authentication or a setup token.
- Store network credentials securely.
- Prevent user media, secrets and databases from entering Git.
- Recover cleanly from interrupted scans and unavailable shares.

#### Deferred from this phase

- Plex and Jellyfin adapters
- Advanced metadata providers
- USB hot-plug polish
- Advanced artwork management

### Documentation outputs

- Catalogue schema
- Source lifecycle
- Supported-format policy
- Scan and rescan behaviour
- Matching and correction rules
- Web UI sitemap for catalogue functions
- Authentication and credential-storage design

### Tests

- Add, remove, rename and replace files.
- Disconnect and reconnect a NAS.
- Interrupt and resume a scan.
- Scan duplicate names and files.
- Preserve manual corrections.
- Scan while playback continues.
- Complete setup from desktop and phone browsers.

### Exit criteria

- Local and SMB/NAS media can be catalogued reliably.
- Users can manage and correct the catalogue through the web UI.
- Playback refers to catalogue IDs, not UI-selected raw paths.
- Routine media setup requires no Linux access.

---

## Phase 4 — Basic real-time channel engine

### Purpose

Create multiple continuously running channels with the minimum scheduling complexity needed for Basic Mode.

### Work packages

#### 4.1 Basic channel model

- Channel number
- Channel name
- Enabled state
- Display order
- Optional logo
- Content pool
- Playback order: sequential or shuffled

#### 4.2 Timeline generation

- Generate a deterministic timeline from media durations.
- Extend the timeline safely into the future.
- Keep previously published timeline entries stable.
- Resolve current and next entries efficiently.
- Calculate exact real-time seek offsets.

#### 4.3 Basic channel web management

- Create a channel.
- Edit number, name and content pool.
- Choose sequential or shuffled playback.
- Reorder, enable, disable and delete channels.
- Preview current and upcoming items in a simple list.
- Warn clearly about empty or invalid channels.

#### 4.4 Failure behaviour

- Skip missing or unreadable media.
- Avoid overlapping entries.
- Repair future timelines after content changes.
- Provide a fallback screen when a channel cannot play.
- Record understandable diagnostic information in the web UI.

#### Deferred to Enhanced Guide Mode or later

- Complex time-of-day rules
- Day-of-week rules
- Seasonal activation
- Detailed programme-grid editing
- Advanced channel templates
- Idents and adverts

### Documentation outputs

- Basic channel schema
- Sequential and shuffled selection rules
- Timeline stability policy
- Schedule-repair procedure
- Channel web UI specification
- Error and fallback behaviour

### Tests

- Multiple channels over multiple days.
- Restart and confirm timeline stability.
- Empty content pool.
- Media removal after scheduling.
- Programmes crossing midnight.
- Daylight-saving transition strategy.
- Rapid channel edits while playback continues.

### Exit criteria

- Multiple Basic Mode channels run continuously.
- Every valid channel resolves current and next content.
- Channel configuration is possible through the web UI.
- Invalid channels fail safely and visibly.

---

## Phase 5 — Basic Mode television experience

### Purpose

Deliver the first complete sofa experience, matching the simplicity of the original inspiration without requiring a full guide.

### Work packages

#### 5.1 Startup flow

- Hide Linux completely.
- Show the NostalgiaBox logo.
- Apply optional CRT static.
- Optionally play a configured ident later without making it mandatory.
- Start Channel 001 by default.
- Support an administrator option to resume the last channel.

#### 5.2 Playback coordination

- Tune to the correct real-time channel offset.
- Change channel up and down.
- Pause and resume.
- Select subtitles and audio tracks.
- Recover from player crashes.
- Recover when a source disappears.
- Keep the real-time schedule authoritative after returning from pause.

The exact pause-across-programme-boundary behaviour must be agreed and documented before implementation is considered complete.

#### 5.3 Compact channel-information overlay

- Channel number
- Channel name
- Current programme title
- Remaining time or start/end time
- Optional progress bar
- Optional channel logo
- Automatic dismissal after a configurable short period
- Manual display through the information button

#### 5.4 Remote input

- Channel up/down
- Information
- Play/pause
- OK/select where required
- Back
- Keyboard equivalents for development
- Consistent key-repeat and debounce handling

#### 5.5 Basic on-TV settings

- View device/network status.
- Toggle CRT transition.
- Change subtitle or audio preferences.
- Access PIN-protected maintenance actions where appropriate.
- Keep advanced setup in the web UI.

#### 5.6 User-friendly errors

- Never show stack traces or terminal output.
- Retry automatically where safe.
- Show a simple message and fallback presentation.
- Provide a diagnostic code visible in the web UI.

### Documentation outputs

- Startup state machine
- Playback state machine
- Remote map
- Channel-overlay specification
- Pause behaviour decision
- Error and fallback catalogue
- Television readability and overscan rules

### Tests

- Complete viewing session using only the target remote.
- Rapid channel changes.
- Pause and resume near programme boundaries.
- Player crash and automatic recovery.
- Network-source loss and return.
- Subtitle and audio selection.
- Cold boot directly into playback.
- Common 1080p display and overscan configurations.

### Exit criteria

- NostalgiaBox boots into a working channel without exposing Linux.
- A user can channel-surf, pause and view programme information using only the remote.
- The experience works without a full guide.
- Failures are understandable and recoverable.

---

## Phase 6 — Basic Mode hardening and first release

### Purpose

Turn the working Basic Mode into a dependable household appliance.

### Work packages

1. Supervise and restart failed services.
2. Add structured logs and health checks.
3. Create backup and restore for settings, catalogue and channel configuration.
4. Define database migrations.
5. Build repeatable provisioning from a clean machine.
6. Add first-run setup and version reporting.
7. Prepare verified update packages and rollback behaviour.
8. Produce an exportable support bundle with secrets removed.
9. Run multi-day playback and schedule-extension tests.
10. Complete user, administrator and recovery documentation.

### Documentation outputs

- Installation guide
- First-run guide
- Basic Mode user guide
- Administration guide
- Backup and restore guide
- Upgrade and rollback guide
- Support and diagnostics guide
- Basic Mode release checklist

### Tests

- Multi-day continuous playback.
- Repeated cold boots and restarts.
- Network interruptions.
- Interrupted scans and database writes.
- Backup and restore to a clean installation.
- Failed update and rollback.
- Low disk space.
- Corrupt or missing media.

### Exit criteria

- A clean reference machine can be converted using documented steps.
- Basic Mode survives routine failures without technical intervention.
- Configuration can be backed up and restored.
- The first usable release can be tagged without depending on Enhanced Guide Mode.

---

## Phase 7 — Enhanced Guide Mode foundation

### Purpose

Add richer navigation to the stable Basic Mode core without changing its underlying behaviour.

### Work packages

1. Define the final public name for the enhanced experience.
2. Add a mode preference while preserving Basic Mode.
3. Design an original NostalgiaBox visual language.
4. Add direct number entry where supported.
5. Build a richer channel-selection screen.
6. Add now/next browsing.
7. Add programme-detail panels.
8. Separate theme tokens from navigation and schedule logic.
9. Confirm all enhanced screens remain fully remote-controlled.

### Documentation outputs

- Enhanced mode naming decision
- Navigation map
- Visual-language specification
- Channel-selection specification
- Programme-detail specification
- Theme architecture

### Tests

- Switch between Basic and Enhanced modes.
- Confirm both use the same channel state and schedules.
- Navigate using remotes with and without number buttons.
- Test many and few channels.
- Test missing artwork and descriptions.

### Exit criteria

- Enhanced navigation works on top of the existing core.
- Basic Mode remains intact and selectable.
- No catalogue, scheduler or playback logic is duplicated.

---

## Phase 8 — Full programme guide and reminders

### Purpose

Deliver the optional original set-top-box-style guide after the core product is already usable.

### Work packages

1. Time-based guide grid.
2. Channel column and logos.
3. Current-time marker.
4. Programme cells sized by duration.
5. Smooth horizontal and vertical navigation.
6. Programme synopsis, episode data and artwork.
7. Set, cancel and trigger reminders.
8. One-action tuning from reminders.
9. Visible-window loading and artwork caching.
10. Selectable guide themes where maintainable.

### Documentation outputs

- EPG interaction specification
- Originality and brand-separation notes
- Reminder lifecycle
- Performance budgets
- Theme specifications

### Tests

- Few and many channels.
- Very short and very long programmes.
- Rapid timeline navigation.
- Missing metadata.
- Reminder behaviour across restart and sleep states.
- Guide responsiveness while scans or playback continue.

### Exit criteria

- Future schedules can be browsed entirely by remote.
- Reminder behaviour is dependable.
- The design is recognisably NostalgiaBox and not a copy of another service.

---

## Phase 9 — Advanced channels and presentation

### Purpose

Add optional depth only after Basic Mode and the enhanced guide are stable.

### Candidate work packages

- Time-of-day and day-of-week scheduling rules
- Seasonal and event channel activation
- Richer starter templates
- Channel themes and colour treatments
- Ident collections
- Schedule preview and conflict explanation
- Favourite channels
- Additional source adapters such as Plex and Jellyfin
- Improved USB storage handling

Each feature requires its own requirements, risk review and acceptance criteria before implementation.

### Exit criteria

- Advanced features are optional.
- Basic Mode remains simple.
- Existing schedules and channel configurations remain compatible.

---

## Phase 10 — Enclosure and physical integration

### Purpose

Create the physical NostalgiaBox appliance around the validated electronics.

### Work packages

1. Measure motherboard, mounting holes, cooling assembly and ports.
2. Preserve blower intake and exhaust paths.
3. Design a removable motherboard tray.
4. Design bottom shell, front fascia and serviceable top cover.
5. Mount SSD and antennas safely.
6. Prototype front buttons and optional display.
7. Validate cable access, assembly order and maintenance.
8. Perform thermal and long-duration playback tests in the new enclosure.
9. Produce printable files, drawings and assembly instructions.

### Exit criteria

- The custom case is mechanically safe and serviceable.
- Temperatures remain within the validated operating envelope.
- All external ports and controls function reliably.
- The enclosure can be reproduced from documentation.

---

## Phase 11 — Optional continuity and future enhancements

### Purpose

Explore features that are not required for the core television appliance.

### Candidate features

- Optional channel and seasonal adverts
- Programme promotions
- “Coming up next” clips
- Advanced idents and bumpers
- Rewind or timeshift
- Profiles and parental controls
- Community channel packs
- Multi-room support
- Physical front-panel channel display

Adverts remain deliberately last. No optional continuity feature may compromise playback reliability or delay core releases.

---

## Cross-phase implementation rules

Every implementation phase must include:

1. Requirements review before coding.
2. Architecture review and ADRs for major decisions.
3. A file-level implementation plan.
4. Automated tests where practical.
5. Manual acceptance tests on the OptiPlex 7050.
6. Documentation updated in the same pull request.
7. Migration and rollback consideration for stored data.
8. Security review for web UI, credentials and updates.
9. Performance review for playback, remote responsiveness and boot time.
10. A demonstration against written exit criteria before the phase is closed.
