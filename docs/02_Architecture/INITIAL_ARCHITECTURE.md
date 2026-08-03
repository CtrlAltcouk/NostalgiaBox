# Initial Architecture

## Status

This is a working architecture for planning. Technology choices remain provisional until individual decisions are accepted through Architecture Decision Records.

## System context

NostalgiaBox is a single-device appliance connected to a television and controlled primarily by a remote.

```text
User + Remote
      |
      v
NostalgiaBox UI
      |
      v
Playback and Channel Runtime
      |
      +--> Schedule Engine
      +--> Media Catalogue
      +--> Configuration and State
      |
      v
Local Media Storage
```

Optional administration may later be available from a local web browser, but normal viewing must not depend on another device.

## Proposed logical components

### 1. Appliance shell

Responsible for:

- system startup and shutdown
- launching the application
- watchdog and recovery behaviour
- suppressing desktop notifications and unrelated operating-system UI
- update and maintenance entry points

### 2. Television frontend

Responsible for:

- full-screen playback presentation
- channel changes
- now/next overlay
- programme guide
- numeric channel entry
- settings and maintenance screens
- remote-friendly focus and navigation
- loading, error and recovery states

The frontend should not own schedule-generation logic.

### 3. Playback coordinator

Responsible for:

- opening the selected media item
- seeking to the correct offset when joining a broadcast in progress
- handling transitions between scheduled items
- monitoring player health
- reporting playback state to the frontend
- recovering from missing or corrupt media

Playback should use an established media engine rather than implementing codecs directly.

### 4. Channel runtime

Responsible for:

- determining the active channel
- resolving what should be playing at the current wall-clock time
- coordinating channel changes with playback
- exposing now/next and guide data
- applying channel-specific presentation settings

### 5. Schedule engine

Responsible for:

- generating continuous channel timelines
- applying programme-selection rules
- preserving episode order where configured
- enforcing repeat restrictions
- inserting idents, bumpers and optional advert blocks
- producing reproducible results from stored rules and state

Schedule generation should be separated from real-time playback so timelines can be inspected and tested independently.

### 6. Media catalogue

Responsible for:

- scanning configured media roots
- identifying programmes, seasons, episodes, films, adverts and idents
- reading or associating metadata
- detecting moved, missing or duplicate files
- exposing media suitable for scheduling

The catalogue stores references and metadata, not the media files themselves.

### 7. Configuration and persistent state

Expected data includes:

- channel definitions
- schedule rules
- media metadata and scan status
- generated timeline entries
- playback and channel state
- episode history and repeat controls
- remote mappings
- application settings
- schema version and migrations

A relational embedded database is the initial preference, but the choice is not yet accepted.

### 8. Administration interface

Potential responsibilities:

- configure media locations
- create and edit channels
- inspect schedule timelines
- trigger scans
- review errors and health
- export or import configuration

Whether this is integrated into the television UI, implemented as a local web interface, or split between both remains open.

## Deployment model

The reference deployment is one Dell OptiPlex 7050 Micro running all core services locally.

No network service should be required for playback after installation and media preparation. Optional metadata retrieval, updates and administration may use the local network or internet.

## Key runtime behaviour

### Tuning into a channel

1. The user selects a channel.
2. The channel runtime reads the current time.
3. It finds the timeline entry covering that time.
4. It calculates the offset from the entry start.
5. The playback coordinator opens the media and seeks to that offset.
6. The frontend displays channel and programme information.

### Programme transition

1. The active timeline entry reaches its end.
2. The runtime resolves the next entry.
3. The playback coordinator transitions without returning to a menu.
4. The guide and now/next state update.
5. Failures follow a documented fallback policy.

### Restart recovery

1. The operating system starts the appliance services automatically.
2. The application loads persistent configuration and validates the database.
3. The runtime selects the configured startup or last-viewed channel.
4. It resolves the current timeline position from wall-clock time.
5. Playback resumes as a broadcast, not from the previous paused frame.

## Architectural constraints

- Core viewing must work offline.
- Normal operation must not expose a desktop or terminal.
- Media codecs must be handled by a mature playback engine.
- Hardware decoding should be used where reliable.
- The UI must remain responsive while media is scanning or schedules are generated.
- Components must be testable without a television attached.
- Missing media must not crash the whole appliance.
- Time and timezone handling must be explicit and testable.
- User media must remain outside the repository.

## Initial risks

| Risk | Impact | Early mitigation |
|---|---|---|
| Incorrect time calculations | Wrong programme or playback offset | Store timezone explicitly and test boundary cases |
| Hardware decoding inconsistencies | Stutter or high CPU usage | Validate representative codecs on reference hardware |
| Schedule complexity grows too early | Delayed usable prototype | Build a simple deterministic scheduler first |
| UI framework is too heavy | Slow startup and navigation | Benchmark candidates on the OptiPlex before acceptance |
| Media naming is inconsistent | Poor catalogue quality | Define supported conventions and clear error reporting |
| Advert and ident rules create gaps | Broken continuous playback | Validate generated timelines before activation |
| Custom enclosure blocks airflow | Heat and instability | Retain Dell chassis and measure temperatures during prototypes |
| Copyrighted assets enter Git history | Legal and repository-size problems | Exclude user media and provide placeholders only |

## Architecture decisions still required

- Base operating system
- UI/application framework
- Media playback engine
- Programming language and service boundaries
- Embedded database
- Schedule-generation model
- Remote-control technology
- Administration approach
- Update and rollback mechanism
- Media storage architecture
