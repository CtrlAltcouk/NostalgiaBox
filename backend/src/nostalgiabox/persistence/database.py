"""SQLAlchemy engine and session construction."""

from sqlalchemy import Engine, event
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool

from nostalgiabox.config.database import is_in_memory_sqlite_url
from nostalgiabox.config.settings import Settings


def create_engine(settings: Settings) -> Engine:
    """Create an engine without connecting or creating schema implicitly."""
    is_sqlite = settings.database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine_options: dict[str, object] = {"connect_args": connect_args}
    if is_in_memory_sqlite_url(settings.database_url):
        engine_options["poolclass"] = StaticPool
    engine = sqlalchemy_create_engine(settings.database_url, **engine_options)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create the core's explicit SQLAlchemy transaction/session boundary."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _enable_sqlite_foreign_keys(
    dbapi_connection: DBAPIConnection,
    _connection_record: ConnectionPoolEntry,
) -> None:
    """Enable SQLite foreign-key enforcement for every engine connection."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
    finally:
        cursor.close()
