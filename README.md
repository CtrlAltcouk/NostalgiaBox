# NostalgiaBox

NostalgiaBox is a standalone retro television appliance designed to recreate the experience of channel surfing through scheduled programmes, adverts, idents and themed channels.

The project targets a dedicated living-room device rather than a general-purpose desktop application. It should boot directly into a remote-controlled TV interface and feel like a real set-top box.

## Project status

Phase 2 core architecture and the one-channel real-time proof are complete as of 2026-08-09.
Phase 3 is the next planned phase; it has not started.

## Initial hardware target

- Dell OptiPlex 7050 Micro
- Intel Core i5-7500T
- 16 GB DDR4 RAM
- 256 GB SSD
- HDMI or DisplayPort video output
- Remote-control input to be selected

## Core goals

- Appliance-style startup with no visible desktop
- Virtual television channels with continuous schedules
- Programme guide and now/next information
- Remote-control-only navigation
- Support for programmes, films, adverts, idents and bumpers
- Authentic channel changes and retro presentation
- Local-first operation without dependence on cloud services
- Maintainable architecture with clear documentation

## Repository structure

```text
NostalgiaBox/
├── docs/
│   ├── 01_Project/
│   ├── 02_Architecture/
│   ├── 03_Hardware/
│   ├── 04_Software/
│   ├── 05_UI_UX/
│   ├── 06_Channel_Engine/
│   ├── 07_Media_Library/
│   ├── 08_Remote_Control/
│   ├── 09_Enclosure/
│   ├── 10_Testing/
│   ├── 11_Release/
│   └── ADR/
├── backend/
├── frontend/
├── installer/
├── enclosure/
├── assets/
├── scripts/
├── testing/
└── .github/
```

## Development approach

The project will use documentation-first planning. Significant technical decisions will be recorded as Architecture Decision Records before implementation begins.

See [ROADMAP.md](ROADMAP.md) and the [documentation index](docs/README.md).

Backend setup, local run, test, lint, typing and migration commands are documented in
[`backend/README.md`](backend/README.md).
