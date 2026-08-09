# NostalgiaBox backend

This directory contains the authoritative NostalgiaBox core service. Phase 2 currently includes
the application foundation, pure deterministic timeline domain, SQLite persistence/proof seed
tooling, and an attach-only MPV JSON IPC player adapter.

## Requirements

- Python 3.13
- Core/development dependencies do not require a C compiler. The optional `linux-input` extra may
  build python-evdev's extension and therefore needs Debian build prerequisites.

All commands below are run from `backend/`.

## Create a development environment

On Debian 13, include the optional Linux input adapter for Task 2.6 reference-hardware proof:

```bash
sudo apt-get install --no-install-recommends build-essential python3-dev
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,linux-input]'
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run the API

```bash
uvicorn nostalgiabox.api:create_app --factory --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health` and returns a stable,
non-sensitive service status.

Development settings use the `NOSTALGIABOX_` environment-variable prefix. For example:

```bash
export NOSTALGIABOX_LOG_LEVEL=DEBUG
export NOSTALGIABOX_DATABASE_URL=sqlite:////tmp/nostalgiabox-dev.db
export NOSTALGIABOX_MPV_SOCKET_PATH=/tmp/nostalgiabox-mpv-dev.sock
export NOSTALGIABOX_MPV_COMMAND_TIMEOUT_SECONDS=2
```

The safe development default uses an ephemeral in-memory SQLite database. Set an ignored
file-backed URL when local persistence is useful. Production deployment must set the database URL
explicitly; the intended value is
`sqlite:////var/lib/nostalgiabox/nostalgiabox.db`.

## Quality checks

```bash
pytest
ruff check .
ruff format --check .
mypy
```

## Alembic and a temporary proof database

The Alembic environment reads the same typed settings as the application. To create or update a
temporary file-backed proof database:

```bash
export NOSTALGIABOX_DATABASE_URL=sqlite:////tmp/nostalgiabox-proof.db
alembic upgrade head
alembic current
```

The initial revision creates only `media_items`, `channels` and `timeline_entries`. Downgrade is
available for migration testing:

```bash
alembic downgrade base
alembic upgrade head
```

Migration authoring remains:

```bash
alembic revision --autogenerate -m "describe approved schema change"
```

Set `NOSTALGIABOX_DATABASE_URL` before migration commands when targeting any database other
than the ignored development database. Never point automated tests at the production path.

## Seed Channel 001 proof data

Create a JSON manifest outside Git. Paths describe operator-supplied media and are not checked for
existence during Task 2.3:

```json
{
  "channel": {"id": "channel-001", "number": 1, "name": "Channel 001"},
  "start_utc": "2026-08-08T18:00:00Z",
  "media": [
    {
      "id": "media-a",
      "title": "Programme A",
      "duration_us": 1320000000,
      "path": "/srv/nostalgiabox/media/test/programme-a.mkv"
    },
    {
      "id": "media-b",
      "title": "Programme B",
      "duration_us": 1500000000,
      "path": "/srv/nostalgiabox/media/test/programme-b.mkv"
    }
  ]
}
```

The target must be explicit and already migrated:

```bash
nostalgiabox-seed \
  --database-url sqlite:////tmp/nostalgiabox-proof.db \
  --manifest /tmp/nostalgiabox-proof.json
```

Running the same command again safely upserts supplied media/channel metadata and replaces only
Channel 001's deterministic timeline. It does not delete unrelated channels or media. Inspect the
proof database where the SQLite CLI is installed:

```bash
sqlite3 /tmp/nostalgiabox-proof.db \
  'SELECT channel_id, media_item_id, start_utc_us, end_utc_us FROM timeline_entries ORDER BY start_utc_us;'
```

## Manually validate the MPV adapter

Task 2.4 attaches to an MPV process launched separately; it never starts or stops that process. On
the reference Dell, first launch an isolated test MPV instance in the `nostalgia` user's active X
session with a dedicated socket that is not the future production socket:

```bash
DISPLAY=:0 mpv \
  --idle=yes \
  --force-window=yes \
  --keep-open=yes \
  --input-ipc-server=/tmp/nostalgiabox-mpv-test.sock \
  --fs \
  --no-border \
  --hwdec=vaapi \
  --audio-device='<the HDMI/ALSA device proven in Phase 1>'
```

Use an unused test socket and the actual Phase 1-proven HDMI/ALSA device value for the Dell. Do not
replace `/opt/nostalgiabox/launch.sh`, alter boot/session services, or use
`/run/nostalgiabox/mpv.sock` for this isolated validation.

In another shell, supply an operator-owned test video explicitly:

```bash
nostalgiabox-mpv-validate \
  --socket /tmp/nostalgiabox-mpv-test.sock \
  --media '/srv/nostalgiabox/media/test/operator-video.mkv' \
  --start-seconds 5 \
  --seek-seconds 10
```

The command proves health, loads at a non-zero position, queries state/position, pauses, resumes,
seeks absolutely and stops. It prompts between visible checks, never reads or modifies the
NostalgiaBox database, and does not launch or terminate MPV. The equivalent source-tree command is
`python -m nostalgiabox.playback.validate` with the same required arguments.

## Run the one-channel proof

Task 2.5 attaches to an already-migrated, explicitly seeded SQLite database and an already-running
MPV socket. It never migrates, seeds or launches MPV. A single resolve/load operation is:

```bash
nostalgiabox-channel-proof \
  --database-url sqlite:////tmp/nostalgiabox-phase25.db \
  --socket /tmp/nostalgiabox-phase25-mpv.sock \
  --channel-number 1 \
  --once
```

For continuous boundary observation, omit `--once` and optionally set `--poll-seconds 0.5`.
Same-entry polls do not reload MPV. Ctrl+C stops the loop and closes the player connection cleanly.
In-memory databases are rejected, and neither the production database nor production MPV socket is
used as a default. `GET /runtime` exposes the latest snapshot only when the API was explicitly
composed with a runtime-state provider; otherwise it returns `{"active":false,"snapshot":null}`.

The complete isolated reference-Dell validation procedure is recorded in Phase 2 `TESTING.md`.

## Run the remote input proof

`evdev==1.9.3` is isolated in the optional `linux-input` extra and imported only by the Linux input
adapter. Windows development continues to use `.[dev]`; automated tests inject fake input devices.
Identify the Consumer Control interface by device metadata or a stable by-id link rather than an
event number, then attach to an isolated, already-running MPV:

```bash
python -m evdev.evtest
nostalgiabox-input-proof \
  --device '/dev/input/by-id/<receiver-consumer-control-event-link>' \
  --socket /tmp/nostalgiabox-phase26-mpv.sock
```

The Nordic 1915:1025 Consumer Control profile maps `KEY_PLAYPAUSE` to logical `PLAY_PAUSE`.
Press/release/repeat produces one action on the press only. When MPV is playing it pauses; when
paused it resumes; idle is reported as a deliberate no-op. The command does not launch or stop MPV,
does not use a database and closes input/player resources on Ctrl+C.

The continuous `nostalgiabox-channel-proof` command now records media/player failures and remains
alive for controlled recovery. Known failed media is suppressed for the rest of the same timeline
entry. Player health is retried at five-second cadence; restored health forces current wall-clock
timeline resolution and a fresh live-offset load. Exact isolated missing/corrupt media and
player-loss procedures are in Phase 2 `TESTING.md`.
