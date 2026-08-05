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

## Startup experience

The intended sequence is:

1. NostalgiaBox logo.
2. Optional CRT-static transition.
3. Channel ident.
4. A classic channel-information banner showing channel number, channel name, current programme and remaining time.
5. Playback starts on the selected startup channel.

The default startup channel is Channel 001. An administrator may instead configure the device to resume the last-viewed channel.

The target from power-on to usable television playback is under five seconds. This is an aspirational product target and must be validated against the selected operating system, firmware and hardware startup limits.

## Real-time television behaviour

Channels operate against real time and continue while not being watched.

If a programme starts at 18:00 and the viewer tunes in at 18:12, playback begins twelve minutes into the programme. Turning the device off does not pause the schedule. On the next startup, the channel reflects what should be broadcasting at that current time.

Changing away from a channel and returning later must rejoin its current real-time position rather than restarting the programme.

## Channel requirements

- The number of channels is chosen by the user.
- Starter channel templates should be provided.
- Users can create, edit, reorder, disable and delete channels.
- Each channel can have its own number, name, logo, colour treatment, ident collection and programme guide entries.
- Channel logos appear as an optional corner watermark.
- Channels may have activation windows, allowing seasonal or event channels to appear only when configured.
- Channel numbering must support direct number entry when the connected remote provides number buttons.

## Media sources

NostalgiaBox must support media from:

- internal storage;
- USB storage;
- SMB/NAS shares;
- Jellyfin;
- Plex.

The first implementation should prioritise local storage and SMB/NAS. Jellyfin and Plex are integrations, not required dependencies.

NostalgiaBox maintains its own catalogue so that users who do not run an external media server receive the full experience.

The TV interface must not expose a normal file browser. Media-source configuration and advanced organisation are handled through the administration web interface.

## Playback requirements

Version 1 should support:

- smooth full-screen playback;
- hardware-accelerated video decoding where supported;
- pausing and resuming the current channel;
- channel changes that preserve the real-time channel schedule;
- common subtitle formats;
- audio-track selection;
- recovery from missing or unreadable media;
- restoration of playback after application restart.

Rewinding live television is deferred until a later release.

## Programme guide

The initial guide should feel familiar to users of classic Sky-style guides without copying Sky branding, artwork or layouts directly.

NostalgiaBox will have its own visual identity and may later provide selectable guide themes.

Version 1 should include:

- current and upcoming programmes;
- channel numbers, names and logos;
- programme start and end times;
- programme synopsis and artwork where available;
- a visible current-time marker;
- navigation by remote control;
- a reminder function.

Search, recording and favourites may be added after the core guide is stable.

## Control methods

Primary control is a simple USB remote. Keyboard input is supported for development, testing and emergency maintenance.

Expected controls include:

- directional navigation;
- OK/select;
- back;
- guide;
- information;
- play/pause;
- channel up/down;
- number entry when available.

## Administration

Advanced configuration is performed through a local web interface, including:

- media sources;
- media scanning and matching;
- channel creation and editing;
- schedule rules;
- channel logos and themes;
- startup behaviour;
- user-facing settings;
- updates, diagnostics and backups.

A limited settings screen may be available on the television. Sensitive or disruptive settings must be PIN protected.

## Advertising and continuity

Advertising is low priority for the initial product. It should not delay the core television experience.

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

## Version 1 definition

Version 1 is successful when a user can:

1. install or boot a configured NostalgiaBox appliance;
2. add local or network media through the web interface;
3. create or edit real-time channels;
4. watch channels from a sofa using only a remote;
5. change channels and open the programme guide;
6. pause and resume playback;
7. restart the appliance without seeing Linux;
8. recover from routine playback and media errors without technical intervention.
