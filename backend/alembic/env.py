from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.accounts import models as accounts_models  # noqa: F401
from app.assets import models as assets_models  # noqa: F401
from app.auth import models as auth_models  # noqa: F401
from app.budgets import models as budgets_models  # noqa: F401
from app.categories import models as categories_models  # noqa: F401
from app.category_rules import models as category_rules_models  # noqa: F401
from app.config import settings
from app.database import Base
from app.goals import models as goals_models  # noqa: F401
from app.holdings import models as holdings_models  # noqa: F401
from app.jobs import models as jobs_models  # noqa: F401
from app.merchants import models as merchants_models  # noqa: F401
from app.metrics import models as metrics_models  # noqa: F401
from app.notifications import models as notifications_models  # noqa: F401
from app.recurring_transactions import models as recurring_transactions_models  # noqa: F401
from app.transactions import models as transactions_models  # noqa: F401

# Import every domain's models module here so autogenerate can see their tables.

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

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
