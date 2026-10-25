from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        if settings is None:
            # BaseSettings loads required fields from the environment or .env.
            app_settings = Settings()  # pyright: ignore[reportCallIssue]
        else:
            app_settings = settings
        app.state.settings = app_settings
        # HTTPX limits each network phase; adapters will enforce the total deadline.
        async with httpx.AsyncClient(
            timeout=app_settings.bank_timeout_seconds,
        ) as client:
            app.state.http_client = client
            yield

    return FastAPI(lifespan=lifespan)


app = create_app()
