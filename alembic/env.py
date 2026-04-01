import os
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from alembic import context

# Import all models so SQLModel registers their metadata before autogenerate
from src.models import ContentItem, PipelineRun, SyncLog  # noqa: F401

# Alembic Config object
config = context.config

# Set up logging from config file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override DB URL from environment variable (Pattern 7)
db_url = os.getenv("DATABASE_URL", "sqlite:///data/pipeline.db")
config.set_main_option("sqlalchemy.url", db_url)

# SQLModel metadata — covers all registered table models
target_metadata = SQLModel.metadata


def ensure_data_dir() -> None:
    """Ensure the data/ directory exists before creating a SQLite DB file."""
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    ensure_data_dir()
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
    """Run migrations in 'online' mode."""
    ensure_data_dir()
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
