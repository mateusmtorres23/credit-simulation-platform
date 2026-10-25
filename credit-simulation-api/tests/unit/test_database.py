import pytest

from app.config import Settings
from app.database import create_database_engine, create_session_factory


@pytest.mark.asyncio
async def test_engine_preserves_credentials_and_session_configuration(settings_data):
    password = "p@ss:/?#%word"
    settings = Settings(
        _env_file=None, **(settings_data | {"postgres_password": password})
    )
    engine = create_database_engine(settings)
    try:
        assert engine.url.drivername == "postgresql+asyncpg"
        assert engine.url.password == password
        assert engine.url.username == settings.postgres_user
        assert engine.url.database == settings.postgres_db
        assert password not in str(engine.url)
        async with create_session_factory(engine)() as session:
            assert session.bind is engine
            assert session.sync_session.expire_on_commit is False
    finally:
        await engine.dispose()
