import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from app import models  # noqa: F401
from app.config import Settings
from app.database import Base, create_database_engine

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        dialect_name="postgresql",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_database_engine(Settings())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
elif context.config.attributes.get("connection") is not None:
    do_run_migrations(context.config.attributes["connection"])
else:
    asyncio.run(run_async_migrations())
