"""Alembic migration environment.

Usage:
  # Generate a new migration from model changes:
  alembic revision --autogenerate -m "describe change"

  # Apply all pending migrations:
  alembic upgrade head

  # Stamp existing DB as baseline (first-time setup on existing DB):
  alembic stamp head

  # Show current revision:
  alembic current
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# Override DB URL with sync driver — alembic uses sync SQLAlchemy
_db_url = os.getenv("POSTGRES_URL", "").replace("+asyncpg", "")
if not _db_url:
    _db_url = "postgresql://vg_user:vg_pass@localhost:5432/vg_hub"

config = context.config
config.set_main_option("sqlalchemy.url", _db_url)

if config.config_file_name:
    fileConfig(config.config_file_name)

# Import ALL models so Alembic sees the full metadata
import modules.suppliers.models       # noqa: F401
import modules.catalog.models         # noqa: F401
import modules.customers.models       # noqa: F401
import modules.markup.models          # noqa: F401
import modules.push_log.models        # noqa: F401
import modules.sync_jobs.models       # noqa: F401
import modules.master_options.models  # noqa: F401
import modules.push_mappings.models   # noqa: F401
import modules.ops_config.models      # noqa: F401
import modules.decorations.models     # noqa: F401
import modules.auth.models            # noqa: F401
import modules.audit_log.models       # noqa: F401

from database import Base
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
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
