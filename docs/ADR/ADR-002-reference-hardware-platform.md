# ADR-002: Reference Hardware Platform

- **Status:** Accepted
- **Date:** 2026-08-03

## Context

NostalgiaBox needs a known reference computer for playback testing, appliance configuration, remote integration and enclosure design. Supporting arbitrary hardware from the beginning would make performance, port placement and thermal behaviour difficult to validate.

## Decision

The initial reference platform is:

- Dell OptiPlex 7050 Micro Form Factor
- Intel Core i5-7500T
- 8 GB DDR4 RAM minimum
- 16 GB planned on the development unit after memory testing
- 256 GB SSD
- External Dell power adapter

The original Dell metal chassis, cooling system and motherboard mounting will remain intact. Any custom enclosure will initially be an outer shell, fascia or mounting assembly around the complete computer.

## Consequences

### Positive

- Development and testing use a known performance baseline.
- Enclosure measurements and port clearances can be repeatable.
- Dell's cooling, grounding and structural design remain intact.
- Replacement memory, storage and power supplies are readily available.
- The used purchase cost is reasonable for a complete x86 platform.

### Negative

- The first enclosure will not be universal.
- Other computers may require separate validation and CAD variants.
- The 7th-generation platform is older and has limited official support for some modern operating systems.
- DisplayPort-to-HDMI behaviour must be tested with the target television.

## Alternatives considered

### Raspberry Pi 5

Rejected for the reference build because the complete system cost was high relative to used business mini PCs, and NostalgiaBox does not require GPIO for its core software.

### Intel NUC

Considered suitable, but not selected because the purchased Dell offered better serviceability and more physical room for future integration at the agreed price.

### Android TV box

Rejected because Linux and hardware support vary substantially between low-cost models, increasing long-term maintenance risk.

### Refurbished thin client

Considered viable for a lower-cost build, but the Dell provides greater CPU headroom and a more predictable x86 Linux environment.
