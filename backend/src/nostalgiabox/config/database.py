"""Database URL classification shared by settings and persistence setup."""

from sqlalchemy.engine import make_url


def is_in_memory_sqlite_url(database_url: str) -> bool:
    """Return whether a SQLAlchemy URL identifies an in-memory SQLite database."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return False

    database = url.database
    if database is None or database == "" or database.lower() in {":memory:", "file::memory:"}:
        return True

    mode = url.query.get("mode")
    if isinstance(mode, tuple):
        return any(value.lower() == "memory" for value in mode)
    return mode is not None and mode.lower() == "memory"
