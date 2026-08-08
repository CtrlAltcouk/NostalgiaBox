"""SQLAlchemy engine and session construction."""

from sqlalchemy import Engine
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.orm import Session, sessionmaker

from nostalgiabox.config.settings import Settings


def create_engine(settings: Settings) -> Engine:
    """Create an engine without connecting or creating schema implicitly."""
    connect_args = (
        {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    )
    return sqlalchemy_create_engine(settings.database_url, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create the core's explicit SQLAlchemy transaction/session boundary."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
