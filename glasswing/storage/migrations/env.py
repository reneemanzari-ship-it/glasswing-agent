from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from glasswing.storage.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# GLASSWING_DB_URL lets the CLI and tests point migrations at a specific
# database file without editing alembic.ini.
db_url = os.environ.get("GLASSWING_DB_URL") or config.get_main_option(
    "sqlalchemy.url", "sqlite:///glasswing.db"
)
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # render_as_batch: SQLite can't ALTER TABLE in place, so later
        # migrations that add/drop/alter columns need batch mode to work
        # at all. Cheap to turn on now, before any migration needs it.
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
