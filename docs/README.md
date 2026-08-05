# NostalgiaBox Documentation

This directory is the project's source of truth for requirements, architecture, hardware, user experience, testing and release decisions.

## Documentation map

- [`01_Project/`](01_Project/) — vision, scope, product requirements, delivery plan and risks
- [`02_Architecture/`](02_Architecture/) — system context, components, data flow and deployment
- [`03_Hardware/`](03_Hardware/) — target computer, inspection, measurements and peripherals
- [`04_Software/`](04_Software/) — operating system, application stack and service design
- [`05_UI_UX/`](05_UI_UX/) — screens, navigation and appliance behaviour
- [`06_Channel_Engine/`](06_Channel_Engine/) — scheduling, timelines, adverts and programme selection
- [`07_Media_Library/`](07_Media_Library/) — media organisation, naming and metadata
- [`08_Remote_Control/`](08_Remote_Control/) — input hardware and button mappings
- [`09_Enclosure/`](09_Enclosure/) — CAD, thermal requirements and assembly
- [`10_Testing/`](10_Testing/) — test strategy and acceptance criteria
- [`11_Release/`](11_Release/) — installation, upgrades, backup and release process
- [`ADR/`](ADR/) — Architecture Decision Records

## Key project documents

- [`01_Project/PRODUCT_REQUIREMENTS.md`](01_Project/PRODUCT_REQUIREMENTS.md) — agreed product behaviour and version-one scope
- [`01_Project/DETAILED_DELIVERY_PLAN.md`](01_Project/DETAILED_DELIVERY_PLAN.md) — phased tasks, tests, outputs and exit criteria
- [`../ROADMAP.md`](../ROADMAP.md) — concise delivery sequence

## Documentation rules

1. Requirements describe behaviour rather than implementation wherever possible.
2. Major technical decisions require an ADR.
3. Unknowns are marked `TBD`; assumptions must not be presented as confirmed facts.
4. Code changes should trace back to a requirement, issue or ADR.
5. Documentation should be updated in the same pull request as the behaviour it describes.
6. A phase is complete only when its acceptance criteria and documentation are complete.
