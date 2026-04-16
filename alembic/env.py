"""Alembic environment config.

Use a SQLAlchemy sync Engine (psycopg dialect) for online migrations.
This provides a SQLAlchemy `Connection` object (with `.dialect`) which
Alembic expects. Running migrations via the Alembic CLI is a top-level
process so creating a sync engine here is safe.

See docs/gotchas.md for Python 3.14 notes and alternatives.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

import app.models  # noqa: F401 — registers all ORM models to Base.metadata
from alembic import context
from app.config import settings
from app.database import Base


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata

# Convert app async URL into a SQLAlchemy sync psycopg URL
# Example: postgresql+asyncpg://user:pass@host:port/db -> postgresql+psycopg://user:pass@host:port/db
_sync_url = settings.database_url.replace(
    "postgresql+asyncpg://", "postgresql+psycopg://"
)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL)."""
    context.configure(
        url=_sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a SQLAlchemy Engine.

    We create a sync Engine using the psycopg dialect and pass a SQLAlchemy
    Connection to Alembic. This ensures `connection.dialect` exists.
    """
    connectable = create_engine(_sync_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
