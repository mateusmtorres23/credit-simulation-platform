from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app import main
from app.config import Settings
from app.database import create_database_engine, create_session_factory


@pytest.fixture
def database_app(monkeypatch, settings_data):
    settings = Settings(_env_file=None, **settings_data)
    engines = []
    sessions = []
    disposed = []
    original_dispose = AsyncEngine.dispose

    async def dispose(engine, close=True):
        disposed.append(engine)
        await original_dispose(engine, close=close)

    monkeypatch.setattr(AsyncEngine, "dispose", dispose)

    class TrackedSession(AsyncSession):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.close = AsyncMock(wraps=self.close)
            self.commit = AsyncMock(wraps=self.commit)
            sessions.append(self)

    def build_engine(config):
        engine = create_database_engine(config)
        engines.append(engine)
        return engine

    def build_factory(engine):
        factory = create_session_factory(engine)
        factory.class_ = TrackedSession
        return factory

    monkeypatch.setattr(main, "create_database_engine", build_engine)
    monkeypatch.setattr(main, "create_session_factory", build_factory)
    return SimpleNamespace(
        app=main.create_app(settings),
        settings=settings,
        engines=engines,
        sessions=sessions,
        disposed=disposed,
    )
