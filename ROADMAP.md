# NostalgiaBox Roadmap

This roadmap describes the intended order of work. Dates are deliberately omitted until the architecture and hardware validation are complete.

## Phase 0 — Project foundation

- Establish the repository and documentation structure
- Record the product vision, scope and non-goals
- Record the confirmed hardware platform
- Create an initial architecture and risk register
- Identify open technical decisions

**Exit criteria:** the project has a documented direction and no implementation begins without an agreed architecture.

## Phase 1 — Hardware validation and base operating system

- Inspect and test the Dell OptiPlex 7050 Micro
- Verify the additional memory module and run a memory test
- Check SSD health, cooling, ports and power supply
- Select and install the base operating system
- Configure automatic startup and recovery behaviour
- Confirm reliable 1080p playback and audio output

**Exit criteria:** the machine boots reliably, plays representative media smoothly and has a repeatable base installation procedure.

## Phase 2 — Proof of concept

- Create a minimal full-screen TV interface
- Implement local media playback
- Define one test channel and a simple schedule
- Tune into a programme at its calculated current position
- Support basic keyboard or remote directional navigation

**Exit criteria:** NostalgiaBox boots into a working test channel and behaves like a continuously broadcasting station.

## Phase 3 — Core platform

- Media scanner and metadata catalogue
- Channel definitions and scheduling rules
- Programme timeline generation
- Playback coordination and recovery
- Persistent settings and application state
- Logging and diagnostics

**Exit criteria:** multiple channels can run from reproducible schedules without manually assembled playlists.

## Phase 4 — Television experience

- Channel up/down and direct number entry
- Now/next banner
- Electronic programme guide
- Channel logos, idents, bumpers and advert blocks
- Remote-control mapping
- Settings and maintenance screens
- Boot and channel-change presentation

**Exit criteria:** the system can be used from the sofa without a keyboard or visible desktop.

## Phase 5 — Enclosure and front panel

- Measure and model the OptiPlex chassis
- Define thermal and access requirements
- Design a retro set-top-box enclosure
- Prototype physical buttons and front display
- Integrate front-panel electronics without compromising cooling
- Produce printable files and assembly documentation

**Exit criteria:** the computer is installed in a safe, serviceable enclosure that looks and behaves like a dedicated appliance.

## Phase 6 — Reliability and release preparation

- Automated and manual test coverage
- Long-running playback and schedule testing
- Power-loss and corrupted-media recovery tests
- Installation and upgrade process
- Backup and restore procedure
- User, administrator and build documentation

**Exit criteria:** a clean machine can be converted into a working NostalgiaBox by following the documented release process.

## Future possibilities

These are not commitments for version 1.0:

- Seasonal and event-based channels
- Multiple eras or regional channel packs
- Web-based administration
- Optional CRT and analogue-signal effects
- Physical channel-number display
- Multiple household profiles
- Import and export of channel configurations
