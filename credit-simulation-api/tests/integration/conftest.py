from contextlib import ExitStack
from pathlib import Path
from secrets import token_hex

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from factories import (
    make_bank_result,
    make_graph,
    make_reason,
    make_session,
    make_simulation,
)
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.database import create_database_engine, create_session_factory
from app.models.enums import BankResultStatus


@pytest.fixture(scope="session")
def postgres_settings():
    # Lazy import keeps unit-only collection independent of Testcontainers/Docker.
    from docker.errors import DockerException
    from testcontainers.community.postgres import PostgresContainer

    password = token_hex(24)
    with ExitStack() as resources:
        try:
            container = resources.enter_context(
                PostgresContainer(
                    "postgres:17-alpine",
                    username="integration_user",
                    password=password,
                    dbname="integration_db",
                    driver=None,
                )
            )
        except (DockerException, OSError, TimeoutError) as error:
            pytest.fail(
                f"Cannot start PostgreSQL Testcontainer; check Docker availability and permissions ({type(error).__name__}).",
                pytrace=False,
            )
        yield Settings(
            _env_file=None,
            postgres_user=container.username,
            postgres_password=password,
            postgres_db=container.dbname,
            postgres_host=container.get_container_host_ip(),
            postgres_port=int(container.get_exposed_port(5432)),
        )


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def migrated_database(postgres_settings):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    engine = create_database_engine(postgres_settings)

    def upgrade(connection):
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    try:
        async with engine.begin() as connection:
            await connection.run_sync(upgrade)
    except (SQLAlchemyError, CommandError) as error:
        detail = str(error).replace(
            postgres_settings.postgres_password.get_secret_value(), "<redacted>"
        )
        pytest.fail(
            f"Alembic upgrade head failed in the test container:\n{detail}",
            pytrace=False,
        )
    finally:
        await engine.dispose()
    return postgres_settings


@pytest_asyncio.fixture
async def engine(migrated_database):
    engine = create_database_engine(migrated_database)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db(engine):
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            async with create_session_factory(engine)(
                bind=connection, join_transaction_mode="create_savepoint"
            ) as session:
                yield session
        finally:
            await transaction.rollback()


@pytest_asyncio.fixture
async def saved_session(db):
    session = make_session()
    db.add(session)
    await db.flush()
    return session


@pytest_asyncio.fixture
async def saved_simulation(db):
    simulation = make_simulation()
    db.add(simulation)
    await db.flush()
    return simulation


@pytest_asyncio.fixture
async def approved_result(db):
    result = make_bank_result()
    db.add(result)
    await db.flush()
    return result


@pytest_asyncio.fixture
async def rejected_result(db):
    result = make_bank_result(status=BankResultStatus.REJECTED)
    db.add(result)
    await db.flush()
    return result


@pytest_asyncio.fixture
async def saved_reason(db):
    reason = make_reason()
    db.add(reason)
    await db.flush()
    return reason


@pytest_asyncio.fixture
async def graph(db):
    graph = make_graph()
    db.add(graph.session)
    await db.flush()
    return graph
