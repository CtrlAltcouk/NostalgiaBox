# NostalgiaBox backend

This directory contains the authoritative NostalgiaBox core service. Task 2.1 provides only
the application, configuration, logging and persistence foundations; channel, timeline and
playback behaviour intentionally belong to later Phase 2 tasks.

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

## Alembic

The Alembic environment reads the same typed settings as the application. Task 2.1 has no
domain schema or revision by design.

```bash
alembic current
alembic upgrade head
alembic revision --autogenerate -m "describe approved schema change"
```

Set `NOSTALGIABOX_DATABASE_URL` before migration commands when targeting any database other
than the ignored development database. Never point automated tests at the production path.
