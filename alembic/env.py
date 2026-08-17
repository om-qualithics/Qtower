from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from apps.api.core.db import Base
from apps.api.core.settings import settings
from apps.api.modules.ai_gateway import models as ai_gateway_models  # noqa: F401
from apps.api.modules.branding import models as branding_models  # noqa: F401
from apps.api.modules.identity import models as identity_models  # noqa: F401
from apps.api.modules.policy import models as policy_models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.migrations_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

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
