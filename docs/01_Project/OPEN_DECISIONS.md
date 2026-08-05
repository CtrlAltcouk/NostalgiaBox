# Open Decisions

These decisions must be resolved before production implementation. Each accepted choice should receive an Architecture Decision Record.

## High priority

### Operating system

Questions:

- Which Linux distribution provides the best balance of stability, hardware support and appliance configuration?
- Should the installation use a minimal image or a lightweight desktop session?
- What is the supported upgrade and rollback path?

Candidates to evaluate:

- Debian stable
- Ubuntu LTS

### Application and UI framework

Requirements:

- fast cold startup on the OptiPlex 7050
- smooth 1080p full-screen interface
- reliable keyboard, infrared and Bluetooth input handling
- clear focus navigation
- maintainable styling and animation
- ability to integrate a mature media player

No framework is accepted yet. Electron should not be assumed without measuring its startup time, memory use and remote-focus behaviour on the reference machine.

### Playback engine

Candidates should be evaluated for:

- hardware-accelerated H.264 and H.265 playback
- accurate seeking into a programme already in progress
- gapless or controlled transitions
- subtitles and multiple audio tracks
- stable control API
- recovery from corrupt files

Likely candidates include mpv and GStreamer. VLC may be included in comparative testing.

### Persistence layer

The initial preference is SQLite because the application is single-device and local-first. The decision must confirm:

- migration strategy
- concurrent access model
- backup and restore process
- generated timeline storage
- resilience after unclean shutdown

### Remote-control approach

Options include:

- HDMI-CEC through the television remote
- USB infrared receiver and conventional remote
- Bluetooth remote
- wireless keyboard-style remote for development only

A reference remote should be selected based on reliability, button availability and Linux support.

## Medium priority

### Media storage

Options:

- internal SSD only
- USB SSD or hard drive
- network share from TrueNAS while keeping the box otherwise standalone
- support for more than one media root

Core playback should fail gracefully when removable or network storage is unavailable.

### Administration interface

Options:

- remote-friendly settings inside the TV interface
- local web administration from another device
- combination of both

The television interface should not become overloaded with complex schedule editing.

### Schedule model

Questions:

- Are complete schedules generated ahead of time or resolved incrementally?
- How far into the future is the guide generated?
- How are schedule changes versioned and activated safely?
- How are episode order, weighted selection and repeat windows represented?
- How are programmes with variable or inaccurate durations handled?

### Time model

The design must explicitly define:

- timezone storage
- daylight-saving transitions
- clock changes while playing
- behaviour when the system clock is incorrect
- whether schedules use local time or UTC internally

### Updates

Questions:

- Should updates be package-based, image-based or Git-based during development?
- How can an update roll back automatically if the UI fails to start?
- Which settings and database files must survive an update?

## Lower priority

- Default visual era and branding direction
- Front-panel display technology
- Physical button controller
- Optional CRT and analogue effects
- Multiple user profiles
- Channel-pack import/export format
- Public plugin or extension system
