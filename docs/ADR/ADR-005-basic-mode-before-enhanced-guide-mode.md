# ADR-005 — Deliver Basic Mode before Enhanced Guide Mode

- **Status:** Accepted
- **Date:** 2026-08-05

## Context

The product vision includes both a simple channel-surfing experience and a richer set-top-box-style experience with channel selection, a full electronic programme guide, reminders and advanced channel features.

Attempting to deliver all of these features together would increase scope, delay validation of the core real-time television behaviour and make it harder to identify whether failures belong to the channel engine, playback system or presentation layer.

The original project inspiration demonstrates that a compelling product can exist with a much simpler interaction model: boot into playback, change continuously running channels and display compact channel information.

The administration web interface is still required early because media sources, scanning, catalogue corrections and channel setup are not suitable for remote-only configuration.

## Decision

NostalgiaBox will be delivered in two layers.

### Basic Mode

Basic Mode is the first complete product and first release target. It includes:

- appliance startup directly into television playback;
- real-time continuously running channels;
- channel up/down navigation;
- compact channel and programme information overlay;
- pause and resume;
- local and network media catalogue;
- simple channel creation and editing;
- administration through the local web UI;
- hidden Linux operation and routine recovery.

Basic Mode does not require:

- a full programme-guide grid;
- reminders;
- advanced channel-selection screens;
- seasonal channels;
- complex scheduling rules;
- adverts or advanced continuity.

### Enhanced Guide Mode

Enhanced Guide Mode is a later optional layer that may include:

- richer channel selection;
- direct channel-number entry;
- now/next browsing;
- a full original electronic programme guide;
- programme-detail screens;
- reminders;
- themes and advanced channel features.

“Enhanced Guide Mode” is a working name. A final original product name will be chosen before public release, and third-party service names will not be used as the feature name.

Both modes will share the same catalogue, database, channel engine, timeline, playback coordinator and web administration interface. Enhanced Guide Mode must not fork or duplicate core logic.

Basic Mode must remain available after Enhanced Guide Mode is introduced.

## Consequences

### Positive

- A usable product can be delivered earlier.
- Core playback and real-time scheduling can be validated without EPG complexity.
- The first release more closely matches the original inspiration.
- Advanced features are built on a proven core rather than assumptions.
- Basic Mode provides a simpler option for children and users who only want channel surfing.
- The web UI can mature alongside the core engine.

### Negative

- Some users may initially expect a full guide that is not present in the first release.
- UI architecture must be planned carefully so Enhanced Guide Mode can be added later without a rewrite.
- Documentation and testing must cover two presentation modes once the enhanced layer exists.

## Guardrails

- Basic Mode must not be treated as a disposable prototype.
- Core APIs must support current/next programme data even before the full guide exists.
- The scheduler must be capable of producing stable timeline entries that a later EPG can display.
- The TV UI must keep playback logic separate from presentation screens.
- The administration web UI remains an early core component.
- Full EPG, reminders, advanced channel selection and adverts cannot block the Basic Mode release.

## Alternatives considered

### Build the full set-top-box experience first

Rejected because it couples too many high-risk systems before the real-time playback core has been proven.

### Build only the simple experience permanently

Rejected because the richer guide and discovery experience remains valuable and should be supported as an optional later layer.

### Create separate Basic and Enhanced applications

Rejected because it would duplicate logic, complicate updates and create incompatible configurations.
