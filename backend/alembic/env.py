"""Alembic environment — takes its database URL from application settings."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.db import models  # noqa: F401  (imported so every table is registered)
from app.db.base import Base, UtcDateTime
from app.db.session import ensure_sqlite_directory

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = get_settings().database_url
ensure_sqlite_directory(database_url)
config.set_main_option("sqlalchemy.url", database_url)
target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """Render custom column types as the plain SQLAlchemy type they produce.

    Autogenerate would otherwise emit `app.db.base.UtcDateTime()` into the
    migration without importing it. UtcDateTime only changes how values are
    converted in Python — the DDL is a timezone-aware DATETIME either way — so
    migrations stay free of application imports.
    """
    if type_ == "type" and isinstance(obj, UtcDateTime):
        autogen_context.imports.add("import sqlalchemy as sa")
        return "sa.DateTime(timezone=True)"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        render_item=render_item,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_item=render_item,
            # SQLite cannot ALTER most things in place; batch mode rewrites the
            # table instead, so migrations behave the same on both backends.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
