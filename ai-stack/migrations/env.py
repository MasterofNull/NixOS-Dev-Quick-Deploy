from __future__ import annotations

import os
import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

BASE_DIR = Path(__file__).resolve().parents[1]
MCP_SERVERS_DIR = BASE_DIR / "mcp-servers"
if str(MCP_SERVERS_DIR) not in sys.path:
    sys.path.append(str(MCP_SERVERS_DIR))

try:
    from aidb.schema import METADATA, document_embeddings_table  # type: ignore  # noqa: E402
except ModuleNotFoundError:
    from schema import METADATA, document_embeddings_table  # type: ignore  # noqa: E402
try:
    from aidb.settings_loader import load_settings  # type: ignore  # noqa: E402
except ModuleNotFoundError:
    from settings_loader import load_settings  # type: ignore  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _get_database_url() -> str:
    settings = load_settings()
    return settings.postgres_dsn


def _prepare_metadata() -> None:
    settings = load_settings()
    document_embeddings_table(METADATA, settings.embedding_dimension)


target_metadata = METADATA


def run_migrations_offline() -> None:
    _prepare_metadata()
    url = _get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    _prepare_metadata()
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _get_database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
