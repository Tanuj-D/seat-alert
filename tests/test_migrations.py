"""Make sure migrations build exactly the schema described in app/db.py."""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app import db


def test_migrations_match_models():
    db.Base.metadata.drop_all(db.engine)
    db.init_db()
    with db.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), db.Base.metadata)
    assert diff == [], f"Models changed without a migration: {diff}. " \
                       "Run: alembic revision --autogenerate -m '...'"


def drop_everything():
    db.Base.metadata.drop_all(db.engine)
    with db.engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")


def test_existing_pre_migration_database_is_adopted():
    # Simulate a database created with create_all before Alembic was added:
    # it has the first migration's tables but no record of any migration.
    drop_everything()
    command.upgrade(Config(str(db.ROOT / "alembic.ini")), db.FIRST_REVISION)
    with db.engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE alembic_version")

    db.init_db()  # must not fail with "table already exists"

    insp = inspect(db.engine)
    assert "alembic_version" in insp.get_table_names()
    # ...and the newer migrations were applied on top.
    assert "title" in {c["name"] for c in insp.get_columns("watches")}
