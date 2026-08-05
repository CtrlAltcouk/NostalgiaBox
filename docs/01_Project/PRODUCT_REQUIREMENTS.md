# NostalgiaBox Product Requirements

## Product statement

NostalgiaBox is a standalone appliance that recreates the experience of watching television in the 1990s and early 2000s using the user's own media library.

## Intended audience

The product should be usable by:

- the project owner and household;
- families and children;
- friends and guests;
- nostalgia-focused users;
- users with or without Plex or Jellyfin;
- future public users if the project is released.

## Desired emotional response

The main experience goals are:

- nostalgia;
- rediscovery;
- surprise;
- the feeling of “I forgot this show existed”.

## Guiding principle

> NostalgiaBox should feel like a television, not a computer. Every feature should support that illusion.

Linux, desktops, terminals, mouse cursors and login screens must not appear during normal operation.

## Product modes and delivery order

NostalgiaBox will support two related experience layers.

### Basic Mode

Basic Mode is the first implementation target and the first usable release. It should closely reproduce the straightforward experience shown by the original YouTube inspiration:

- turn on the appliance and enter television playback;
- watch continuously running real-time channels;
- change channels with a simple remote;
- briefly display channel and programme information;
- pause and resume playback;
- perform administration through the local web interface.

Basic Mode intentionally excludes the full programme-grid interface, advanced channel-selection screens, reminders and complex scheduling features. Its purpose is to prove and deliver the core experience quickly without creating throwaway architecture.

### Enhanced Guide Mode

Enhanced Guide Mode is a later optional layer built on the same catalogue, scheduler, playback engine and administration web interface. It may add:

- a richer channel-selection interface;
- direct channel-number entry;
- now/next browsing;
- a full electronic programme guide;
- programme-detail screens;
- reminders;
- additional themes and presentation options;
- more advanced channel and scheduling features.

“Enhanced Guide Mode” is a working project name and may be changed before release. The project must not use third-party product names or branding as the public name of this feature.

Basic Mode must remain available after Enhanced Guide Mode is introduced. Enhanced Guide Mode must extend shared components rather than create a separate incompatible product or duplicate core logic.

## Startup experience

The intended sequence is:

1. NostalgiaBox logo.
2. Optional CRT-static transition.
3. Optional channel ident where configured.
4. A compact channel-information banner showing channel number, channel name, current programme and remaining time.
5. Playback starts on the selected startup channel.

The default startup channel is Channel 001. An administrator may instead configure the device to resume the last-viewed channel.

The target from power-on to usable television playback is under five seconds. This is an aspirational product target and must be validated against the selected operating system, firmware and hardware startup limits.

## Real-time television behaviour

Channels operate against real time and continue while not being watched.

If a programme starts at 18:00 and the viewer tunes in at 18:12, playback begins twelve minutes into the programme. Turning the device off does not pause the schedule. On the next startup, the channel reflects what should be broadcasting at that current time.

Changing away from a channel and returning later must rejoin its current real-time position rather than restarting the programme.

## Channel requirements

### Basic Mode requirements

- The user chooses how many channels exist.
- Starter channel templates may be provided.
- Users can create, edit, reorder, enable, disable and delete channels through the web UI.
- Each channel has at minimum a number, name, enabled state and content pool.
- Each channel can optionally have a logo and corner watermark.
- Basic scheduling may support sequential or shuffled playback from a content pool.
- Empty or invalid channels must fail gracefully and be clearly reported in the web UI.

### Enhanced Guide Mode requirements

Later releases may add:

- richer channel-selection screens;
- direct number entry where the remote supports number buttons;
- channel colours and themes;
- ident collections;
- advanced time-of-day and day-of-week rules;
- seasonal and event activation windows;
- schedule previews and programme-discovery features.

## Media sources

NostalgiaBox must ultimately support media from:

- internal storage;
- USB storage;
- SMB/NAS shares;
- Jellyfin;
- Plex.

The first implementation should prioritise local storage and SMB/NAS. USB support should follow once local source handling is reliable. Jellyfin and Plex are later integrations, not required dependencies.

NostalgiaBox maintains its own catalogue so that users who do not run an external media server receive the full experience.

The TV interface must not expose a normal file browser. Media-source configuration, scanning and advanced organisation are handled through the administration web interface.

## Playback requirements

Basic Mode should support:

- smooth full-screen playback;
- hardware-accelerated video decoding where supported;
- pausing and resuming the current channel;
- channel changes that preserve the real-time channel schedule;
- common subtitle formats;
- audio-track selection;
- recovery from missing or unreadable media;
- restoration of playback after application restart.

Rewinding live television is deferred until a later release.

## Channel information overlay

Basic Mode must include a compact overlay shown during startup and channel changes. It should display:

- channel number;
- channel name;
- current programme title;
- remaining time or start/end time;
- optional progress indicator;
- optional channel logo.

The overlay must disappear automatically and must not require a programme guide to function.

## Programme guide

A full programme guide is not required for the first Basic Mode release.

Enhanced Guide Mode should introduce an original NostalgiaBox guide that feels familiar to users of classic set-top-box guides without copying third-party branding, artwork or layouts directly.

The later guide may include:

- current and upcoming programmes;
- channel numbers, names and logos;
- programme start and end times;
- programme synopsis and artwork where available;
- a visible current-time marker;
- navigation by remote control;
- reminders.

Search, recording and favourites remain later possibilities.

## Control methods

Primary control is a simple USB remote. Keyboard input is supported for development, testing and emergency maintenance.

Basic Mode controls should include:

- directional navigation where needed;
- OK/select;
- back;
- information;
- play/pause;
- channel up/down.

Number entry, guide and richer navigation controls may be introduced with Enhanced Guide Mode when supported by the selected remote.

## Administration web interface

The local web interface remains a core requirement from the early implementation stages. It is not deferred with Enhanced Guide Mode.

It should provide, in controlled increments:

- first-run setup;
- media-source configuration;
- media scanning and matching;
- manual catalogue corrections;
- basic channel creation and editing;
- content-pool configuration;
- startup behaviour;
- CRT-effect toggle;
- remote settings;
- device status and diagnostics;
- updates, backups and restore.

Advanced scheduling, guide themes, seasonal channels and similar features can be added to the same web interface when their corresponding product phases begin.

A limited settings screen may be available on the television. Sensitive or disruptive settings must be PIN protected.

## Advertising and continuity

Advertising is low priority and must not delay Basic Mode, Enhanced Guide Mode or core reliability work.

A later phase may add optional:

- channel-specific adverts;
- seasonal adverts;
- station idents;
- programme promotions;
- “coming up next” clips.

Weather inserts are not currently planned.

## Storage and copyrighted content

The repository, installer and release packages must not contain copyrighted programmes, adverts, channel logos or recordings unless the project has the legal right to distribute them.

Users are responsible for supplying and lawfully using their own media. Sample development assets must be original, licensed or public domain.

## Basic Mode release definition

Basic Mode is successful when a user can:

1. install or boot a configured NostalgiaBox appliance;
2. add local or network media through the web interface;
3. scan and correct the internal media catalogue;
4. create or edit simple real-time channels through the web interface;
5. watch and change channels from a sofa using a remote;
6. see a compact channel-information overlay;
7. pause and resume playback;
8. restart the appliance without seeing Linux;
9. recover from routine playback and media errors without technical intervention.

A full EPG, reminders, advanced channel-selection interface, seasonal channels and adverts are not required for Basic Mode completion.

## Enhanced Guide Mode release definition

Enhanced Guide Mode is successful when the user can optionally enable a richer set-top-box experience that includes channel discovery, a full original programme guide, programme details and reminders without weakening or replacing Basic Mode.
