# NostalgiaBox Product Modes

This document defines the two supported television experiences. It prevents Basic Mode from being treated as a temporary prototype and prevents Enhanced Guide Mode from duplicating or replacing the core platform.

## Product rule

Basic Mode and Enhanced Guide Mode are permanent user-selectable product modes.

- **Basic Mode** is for users who want the simplest possible television experience.
- **Enhanced Guide Mode** adds richer discovery and guide functionality for users who want it.
- Both modes use the same media catalogue, database, schedules, channel timelines, playback coordinator, settings and administration web interface.
- Adding Enhanced Guide Mode must not remove, degrade or complicate Basic Mode.

## Basic Mode purpose

Basic Mode should reproduce the direct, uncomplicated experience demonstrated by the original project inspiration:

1. Power on the appliance.
2. Boot directly into a playing channel.
3. Change channels using channel up/down.
4. Show a compact channel-information overlay when tuning or requesting information.
5. Pause and resume playback.
6. Perform all advanced administration through the web UI.

Basic Mode is a complete supported feature, not a development stage.

## Basic Mode requirements

### Television interface

- Start directly in full-screen playback.
- Default to Channel 001, with an administrator option to resume the previous channel.
- Support channel up and channel down.
- Display channel number, channel name, current programme and remaining time.
- Display an optional channel logo watermark.
- Support play/pause.
- Support subtitles and audio-track selection where available.
- Use friendly recovery screens when media is unavailable.
- Never expose Linux during normal use.

### Configuration

The television interface may expose only safe, frequently used settings. Media and system administration remain in the web UI.

### Web administration

Basic Mode still includes the full administration foundation required to:

- add internal, USB and SMB/NAS media sources;
- scan and correct the media catalogue;
- create, edit, enable, disable, order and number channels;
- configure startup behaviour;
- configure the CRT transition and basic presentation options;
- inspect health, diagnostics and storage status;
- back up and restore configuration;
- install supported updates.

### Scheduling foundation

Basic Mode may initially expose simple scheduling controls, but its underlying timeline must remain compatible with future guide features. It must provide reliable current and next programme data even when no full EPG is shown.

## Enhanced Guide Mode purpose

Enhanced Guide Mode adds programme discovery and set-top-box-style navigation without changing the underlying playback and scheduling behaviour.

Possible features include:

- channel-selection screens;
- direct channel-number entry;
- now/next browsing;
- a full original electronic programme guide;
- programme-detail pages;
- reminders;
- richer channel templates and scheduling rules;
- selectable visual themes;
- seasonal and event channel controls.

“Enhanced Guide Mode” is a working name and will be replaced with an original public-facing name before release if a better name is chosen.

## Shared platform requirements

The following components must remain shared:

- media-source adapters;
- media catalogue and metadata;
- channel records and numbering;
- scheduling and timeline generation;
- current/next programme resolution;
- playback coordination;
- remote-input abstraction;
- persistent settings;
- administration API and web UI;
- logging, health and update systems.

Presentation code must not contain duplicated scheduling or playback logic.

## Mode selection

The selected television mode will be configurable through the administration web UI. A safe PIN-protected television setting may also be provided later.

Changing mode must:

- preserve channels, schedules and media configuration;
- preserve the current or configured startup channel;
- require no media rescan;
- require no database conversion beyond normal compatible migrations;
- allow the user to return to Basic Mode at any time.

## Acceptance criteria

### Basic Mode release

Basic Mode is complete when:

1. It boots into full-screen television playback without exposing Linux.
2. Real-time channels continue while not viewed or while the appliance is off.
3. Channel up/down works reliably using the target remote.
4. The compact information overlay is accurate.
5. Pause/resume and routine playback recovery work.
6. Media and channels can be administered without direct Linux access.
7. The system can operate for extended viewing sessions without requiring a keyboard.
8. Its APIs and stored data remain suitable for a future guide interface.

### Enhanced Guide Mode release

Enhanced Guide Mode is complete only when:

1. It uses the same channels and schedules as Basic Mode.
2. Its guide information matches actual playback timelines.
3. Mode switching preserves all user configuration.
4. Basic Mode remains fully available and independently tested.
5. Enhanced features do not reduce channel-switching or playback reliability.

## Required test coverage after both modes exist

Every release must test:

- fresh installation into Basic Mode;
- upgrade while remaining in Basic Mode;
- switching from Basic to Enhanced Guide Mode;
- switching back to Basic Mode;
- shared channel and schedule consistency;
- playback behaviour in both modes;
- remote navigation in both modes;
- web administration changes reflected in both modes;
- database migration and rollback compatibility.

## Explicit non-goals for the first Basic Mode release

The following must not block the first Basic Mode release:

- full guide grid;
- reminders;
- advanced channel-selection interface;
- adverts;
- complex continuity packages;
- rewind;
- multiple guide themes;
- physical front-panel integration.
