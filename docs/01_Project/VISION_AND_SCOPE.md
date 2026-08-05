# Vision and Scope

## Vision

NostalgiaBox will be a dedicated living-room appliance that recreates the experience of watching scheduled television rather than browsing a media library.

A user should be able to power it on, pick up a remote, change channels and discover what is currently playing. Programmes should appear within continuous schedules alongside appropriate idents, bumpers and optional advert blocks.

The finished product should feel intentional and self-contained, not like a desktop computer running a media player.

## Product principles

1. **Television first** — interaction should resemble a set-top box, not a streaming catalogue.
2. **Remote first** — normal use must not require a keyboard, mouse or terminal.
3. **Local first** — core operation should continue without internet access.
4. **Deterministic and recoverable** — schedules and playback position should be reproducible after restart.
5. **Maintainable** — modules should have clear responsibilities and documented interfaces.
6. **Authentic but configurable** — presentation may be nostalgic without forcing one era or broadcaster.
7. **Legal media ownership** — NostalgiaBox organises user-supplied media; it will not distribute copyrighted programmes, adverts or branding.

## Version 1 goals

- Boot directly into the television experience
- Play user-supplied local media
- Define multiple numbered channels
- Generate continuous programme timelines
- Join the currently scheduled item at the correct playback position
- Provide channel up/down and direct-number tuning
- Provide now/next information and an electronic programme guide
- Support idents, bumpers and optional advert blocks
- Operate reliably with a conventional remote control
- Provide a safe settings or maintenance interface
- Run on the documented Dell OptiPlex 7050 Micro reference hardware
- Provide repeatable installation, backup and recovery documentation

## Non-goals for version 1

- Hosting media for other households over the internet
- Acting as a general Plex, Jellyfin or Kodi replacement
- Live broadcast television reception
- Cloud accounts or subscription services
- Automatic downloading of copyrighted media
- AI-generated video or programme content
- Supporting every mini-PC model and operating system
- Mobile applications
- Multi-room synchronised playback
- A public plugin marketplace

## Target user experience

1. The user presses power or wakes the device.
2. NostalgiaBox starts without exposing the operating-system desktop.
3. The last viewed or configured startup channel appears.
4. Channel changes are immediate enough to feel natural and show clear feedback.
5. The user can open a guide, inspect now/next information and return to viewing.
6. Failures show a simple recoverable message rather than a terminal or crash dialog.
7. Administrative actions are separated from normal viewing.

## Success criteria

Version 1 is successful when a clean reference machine can be installed from the documentation and used for prolonged remote-only channel viewing without routine technical intervention.

## Open product questions

- Which historical era should provide the default visual language?
- Should schedules follow wall-clock time exclusively, or support an accelerated/demo mode?
- How much control should version 1 expose for automatic schedule generation?
- Should adverts be optional per channel, globally, or both?
- What remote hardware will become the reference input device?
