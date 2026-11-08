from alembic import context
from sqlalchemy import create_engine

from app.config import DATABASE_URL
from app.db import Base

# Logging is left alone on purpose: calling logging.config.fileConfig here would
# disable uvicorn's loggers when migrations run at app startup.

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=DATABASE_URL, target_metadata=target_metadata,
                      literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with create_engine(DATABASE_URL).connect() as conn:
        # render_as_batch lets ALTER TABLE migrations work on SQLite too.
        context.configure(connection=conn, target_metadata=target_metadata,
                          render_as_batch=True, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
