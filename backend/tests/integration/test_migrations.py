"""Initial Alembic migration lifecycle tests on temporary SQLite files."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from pytest import MonkeyPatch
from sqlalchemy import inspect

from nostalgiabox.config.settings import Settings
from nostalgiabox.persistence.database import create_engine

_BACKEND_ROOT = Path(__file__).parents[2]
_TABLES = {
    "alembic_version",
    "catalogue_items",
    "channels",
    "media_files",
    "media_items",
    "media_sources",
    "playable_renditions",
    "timeline_entries",
}


def test_initial_migration_upgrade_repeat_downgrade_and_reupgrade(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("NOSTALGIABOX_DATABASE_URL", database_url)
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))

    command.upgrade(config, "head")
    command.upgrade(config, "head")
    assert _table_names(database_url) == _TABLES
    assert _current_revision(database_url) == "20260809_0002"

    command.downgrade(config, "base")
    assert _table_names(database_url) == {"alembic_version"}

    command.upgrade(config, "head")
    assert _table_names(database_url) == _TABLES


def _table_names(database_url: str) -> set[str]:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _current_revision(database_url: str) -> str | None:
    engine = create_engine(Settings(environment="test", database_url=database_url))
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()
