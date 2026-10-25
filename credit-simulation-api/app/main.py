from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.config import Settings
from app.database import create_database_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        if settings is None:
            # BaseSettings loads required fields from the environment or .env.
            app_settings = Settings()  # pyright: ignore[reportCallIssue]
        else:
            app_settings = settings
        app.state.settings = app_settings
        engine = create_database_engine(app_settings)
        try:
            app.state.database_engine = engine
            app.state.session_factory = create_session_factory(engine)
            # HTTPX limits each network phase; adapters enforce the total deadline.
            async with httpx.AsyncClient(
                timeout=app_settings.bank_timeout_seconds,
            ) as client:
                app.state.http_client = client
                yield
        finally:
            await engine.dispose()

    return FastAPI(lifespan=lifespan)


app = create_app()
