"""Command-line entry point for explicit proof-database seeding."""

import argparse
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.engine import make_url

from nostalgiabox.config.database import is_in_memory_sqlite_url
from nostalgiabox.config.settings import Settings
from nostalgiabox.domain.exceptions import TimelineDomainError
from nostalgiabox.persistence.database import create_engine, create_session_factory
from nostalgiabox.persistence.errors import PersistenceError, SeedError
from nostalgiabox.seed.manifest import load_manifest
from nostalgiabox.seed.service import ensure_seed_schema, seed_manifest


def seed_database(database_url: str, manifest_path: Path) -> int:
    """Seed an explicitly targeted, migrated persistent SQLite database."""
    if make_url(database_url).get_backend_name() != "sqlite":
        raise SeedError("proof seeding requires an explicit SQLite database URL")
    if is_in_memory_sqlite_url(database_url):
        raise SeedError(
            "proof seeding requires a persistent database URL; in-memory is not allowed"
        )

    manifest = load_manifest(manifest_path)
    settings = Settings(database_url=database_url)
    engine = create_engine(settings)
    try:
        ensure_seed_schema(engine)
        session_factory = create_session_factory(engine)
        with session_factory.begin() as session:
            timeline = seed_manifest(session, manifest)
        return len(timeline.entries)
    finally:
        engine.dispose()


def main() -> None:
    """Parse explicit seed inputs and report a concise result."""
    parser = argparse.ArgumentParser(description="Seed a migrated NostalgiaBox proof database")
    parser.add_argument("--database-url", required=True, help="explicit persistent SQLite URL")
    parser.add_argument("--manifest", required=True, type=Path, help="Channel 001 JSON manifest")
    args = parser.parse_args()

    try:
        entry_count = seed_database(args.database_url, args.manifest)
    except (OSError, ValueError, ValidationError, TimelineDomainError, PersistenceError) as error:
        parser.error(str(error))
    print(f"Seeded {entry_count} timeline entries successfully.")


if __name__ == "__main__":
    main()
