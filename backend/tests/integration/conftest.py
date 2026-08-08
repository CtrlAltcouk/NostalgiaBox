"""Isolated in-memory persistence fixtures."""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from nostalgiabox.config.settings import Settings
from nostalgiabox.persistence import models as persistence_models
from nostalgiabox.persistence.database import create_engine, create_session_factory


@pytest.fixture
def persistence_engine() -> Iterator[Engine]:
    """Create an isolated SQLite engine with the approved metadata."""
    engine = create_engine(Settings(environment="test"))
    persistence_models.Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def persistence_session(persistence_engine: Engine) -> Iterator[Session]:
    """Yield a session whose changes are rolled back after each test."""
    session = create_session_factory(persistence_engine)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
