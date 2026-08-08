# NostalgiaBox backend

This directory contains the authoritative NostalgiaBox core service. Phase 2 currently includes
the application foundation, pure deterministic timeline domain, and SQLite persistence/proof seed
tooling. Playback behavior remains in later Phase 2 tasks.

## Requirements

- Python 3.13
- A supported C compiler is not expected to be necessary for the declared dependencies

All commands below are run from `backend/`.

## Create a development environment

On Debian 13:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
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
