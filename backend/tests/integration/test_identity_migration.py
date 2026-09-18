"""Task 3.5 additive lifecycle and evidence constraints on Alembic-created SQLite."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from nostalgiabox.config.settings import Settings
from nostalgiabox.persistence.database import create_engine


def test_populated_0005_upgrade_evidence_guards_downgrade_reupgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'identity-lifecycle.db'}"
    monkeypatch.setenv("NOSTALGIABOX_DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    command.upgrade(config, "20260914_0005")
    engine = create_engine(Settings(environment="test", database_url=url))
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO media_sources (id, kind) VALUES ('s', 'local')"))
        connection.execute(text("INSERT INTO media_items VALUES ('item', 'Title', 1, '/legacy')"))
        connection.execute(text("INSERT INTO catalogue_items VALUES ('item')"))
        for file_id in ("a", "b"):
            connection.execute(
                text(
                    "INSERT INTO media_files (id, source_id, normalized_relative_locator, "
                    "original_relative_locator) VALUES (:id, 's', :id, :id)"
                ),
                {"id": file_id},
            )
        connection.execute(
            text("INSERT INTO playable_renditions VALUES ('r', 'item', 'a', 0, 1, 1, 0, 0)")
        )
        before = [
            tuple(row)
            for row in connection.execute(text("SELECT * FROM media_files ORDER BY id")).all()
        ]
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    command.check(config)
    with engine.begin() as connection:
        assert [
            tuple(row[:-1])
            for row in connection.execute(text("SELECT * FROM media_files ORDER BY id")).all()
        ] == before
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        for evidence_id, kind, algorithm in (
            ("q", "quick", "sha256-sampled"),
            ("f", "full_sha256", "sha256"),
        ):
            connection.execute(
                text(
                    "INSERT INTO content_fingerprints VALUES (:id, 'a', 'snapshot', :kind, "
                    ":algorithm, 1, :digest, 3)"
                ),
                {"id": evidence_id, "kind": kind, "algorithm": algorithm, "digest": "a" * 64},
            )
        connection.execute(
            text("INSERT INTO content_groups VALUES ('g', 'sha256', 1, :d, 3)"), {"d": "a" * 64}
        )
        connection.execute(text("INSERT INTO content_group_members VALUES ('g', 'f')"))
        connection.execute(
            text(
                "INSERT INTO identity_transitions VALUES ('t', 'replacement', 'a', 'b', "
                "'before', 'after', 'test', 1)"
            )
        )
        connection.execute(text("INSERT INTO identity_retirements VALUES ('a', 't')"))
        connection.execute(text("INSERT INTO identity_discoveries VALUES ('b', 1)"))
    for statement in (
        "INSERT INTO content_group_members VALUES ('g', 'q')",
        "UPDATE content_fingerprints SET digest = 'bad' WHERE id = 'f'",
        "DELETE FROM content_fingerprints WHERE id = 'q'",
        "UPDATE identity_transitions SET reason = 'rewrite'",
        "DELETE FROM identity_retirements",
        "UPDATE identity_discoveries SET generation = 2",
        "DELETE FROM content_groups",
        "DELETE FROM content_group_members",
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text(statement))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO content_fingerprints VALUES ('bad', 'a', 'snapshot', 'full_sha256', "
                "'sha256', 1, :d, 3)"
            ),
            {"d": "z" * 64},
        )
    command.downgrade(config, "20260914_0005")
    with engine.connect() as connection:
        assert [
            tuple(row)
            for row in connection.execute(text("SELECT * FROM media_files ORDER BY id")).all()
        ] == before
        assert (
            connection.execute(text("SELECT media_file_id FROM playable_renditions")).scalar()
            == "a"
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        assert "content_fingerprints" not in inspect(connection).get_table_names()
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()
