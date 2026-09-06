import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from api.core.config import get_settings
from api.core.database import Base

# Importing every module's models registers them on Base.metadata so that
# autogenerate sees them. New modules must be added here.
from api.modules.geography import models as _geography_models  # noqa: F401
from api.modules.identity import models as _identity_models  # noqa: F401
from api.modules.marketplace import models as _marketplace_models  # noqa: F401
from api.modules.skills import concepts as _skills_concepts  # noqa: F401
from api.modules.skills import content as _skills_content  # noqa: F401
from api.modules.skills import hierarchy as _skills_hierarchy  # noqa: F401
from api.modules.skills import models as _skills_models  # noqa: F401

config = context.config

# Callers may pre-set the URL (the test suite points it at a container). Only
# fall back to environment configuration when they have not.
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Indexes created with raw SQL (GIN / trigram / tsvector) are invisible to
# SQLAlchemy's metadata, so autogenerate reports them as orphans and proposes
# DROPping them. Accepting that silently breaks search. Anything created by
# op.execute() in a migration must be listed here.
MANUALLY_MANAGED_INDEXES = {
    "ix_skills_search_vector",
    "ix_skills_name_en_trgm",
    "ix_skill_aliases_form_trgm",
    "ix_jobs_search_vector",
    "ix_courses_search_vector",
}


def include_object(obj, name, type_, reflected, compare_to):  # noqa: ANN001, ANN201
    return not (type_ == "index" and name in MANUALLY_MANAGED_INDEXES)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
