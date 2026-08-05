# ADR-003 — Use a real-time channel model

- **Status:** Accepted
- **Date:** 2026-08-05

## Context

NostalgiaBox is intended to recreate television rather than present an on-demand media library. The system therefore needs a clear rule for what happens when a viewer tunes into a channel, changes away, restarts the application or powers the device off for several days.

Considered approaches included:

1. restarting a channel playlist whenever it is selected;
2. continuing a private playlist position only while the application runs;
3. resolving every channel against a continuously advancing real-world schedule.

## Decision

NostalgiaBox will use a real-time channel model.

Each channel has a timeline based on wall-clock time. When the viewer tunes into a channel, the system resolves the programme active at that instant and seeks to the corresponding elapsed position.

Example: if a programme is scheduled from 18:00 to 18:30 and the channel is selected at 18:12, playback begins approximately twelve minutes into the programme.

The schedule continues while:

- another channel is being watched;
- playback on the current channel is paused;
- the application is restarted;
- the appliance is powered off.

When returning to a channel, the viewer rejoins its current real-time position rather than the position at which they left it.

## Consequences

### Positive

- Channel surfing behaves like broadcast television.
- The programme guide, now/next banner and reminders share one authoritative timeline.
- Turning the device off does not create unrealistic frozen channels.
- Multiple users can understand what “on now” means consistently.
- Seasonal and time-of-day scheduling can be added naturally.

### Negative

- Accurate duration metadata is essential.
- Missing media requires deterministic fallback behaviour.
- Timezone, clock correction and daylight-saving transitions must be designed carefully.
- Pausing a channel creates a temporary local playback state that differs from its live schedule.
- Schedule generation and playback coordination are more complex than a simple playlist.

## Pause behaviour

Pausing is permitted for usability. While paused, the real-time channel schedule continues in the background.

The detailed behaviour when resuming, changing channel or crossing a programme boundary while paused will be specified during playback design. The implementation must clearly distinguish:

- the channel's live schedule position; and
- the viewer's temporary paused playback position.

## Validation requirements

The proof of concept must demonstrate:

- tuning at several offsets within a programme;
- correct transition at programme boundaries;
- restarting and rejoining the correct live position;
- changing away and back without restarting the programme;
- defined handling for clock and timezone changes;
- defined handling for missing or corrupt scheduled media.
