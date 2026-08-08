"""Database infrastructure tests with isolated temporary storage."""

from pathlib import Path

from sqlalchemy import text

from nostalgiabox.config.settings import Settings
from nostalgiabox.persistence import create_engine, create_session_factory


def test_database_uses_configured_temporary_path(tmp_path: Path) -> None:
    database_path = tmp_path / "test.db"
    settings = Settings(environment="test", database_url=f"sqlite+pysqlite:///{database_path}")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        assert session.scalar(text("SELECT 1")) == 1

    engine.dispose()
    assert database_path.is_file()
    assert str(database_path).startswith(str(tmp_path))
