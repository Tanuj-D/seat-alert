"""Make sure migrations build exactly the schema described in app/db.py."""

from alembic.autogenerate import compare_metadata
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


def test_existing_pre_migration_database_is_adopted():
    # Simulate a database created with create_all before Alembic was added.
    db.Base.metadata.drop_all(db.engine)
    with db.engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    db.Base.metadata.create_all(db.engine)

    db.init_db()  # must not fail with "table already exists"
    assert "alembic_version" in inspect(db.engine).get_table_names()
