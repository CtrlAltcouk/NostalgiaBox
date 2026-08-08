"""Database infrastructure tests with isolated temporary storage."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from nostalgiabox.config.settings import Settings
from nostalgiabox.persistence import create_engine, create_session_factory


def test_in_memory_database_is_shared_across_threads() -> None:
    settings = Settings(environment="test", database_url="sqlite+pysqlite:///:memory:")
    engine = create_engine(settings)

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE thread_probe (value TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO thread_probe (value) VALUES ('shared')"))

    def read_from_another_thread() -> str | None:
        with engine.connect() as connection:
            return cast(str | None, connection.scalar(text("SELECT value FROM thread_probe")))

    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(read_from_another_thread).result()

    engine.dispose()
    assert result == "shared"


def test_database_uses_configured_temporary_path(tmp_path: Path) -> None:
    database_path = tmp_path / "test.db"
    settings = Settings(environment="test", database_url=f"sqlite+pysqlite:///{database_path}")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    assert not isinstance(engine.pool, StaticPool)

    with session_factory() as session:
        assert session.scalar(text("SELECT 1")) == 1

    engine.dispose()
    assert database_path.is_file()
    assert str(database_path).startswith(str(tmp_path))
