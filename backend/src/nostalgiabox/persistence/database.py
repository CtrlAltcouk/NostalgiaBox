"""SQLAlchemy engine and session construction."""

from sqlalchemy import Engine
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from nostalgiabox.config.database import is_in_memory_sqlite_url
from nostalgiabox.config.settings import Settings


def create_engine(settings: Settings) -> Engine:
    """Create an engine without connecting or creating schema implicitly."""
    is_sqlite = settings.database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine_options: dict[str, object] = {"connect_args": connect_args}
    if is_in_memory_sqlite_url(settings.database_url):
        engine_options["poolclass"] = StaticPool
    return sqlalchemy_create_engine(settings.database_url, **engine_options)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create the core's explicit SQLAlchemy transaction/session boundary."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
