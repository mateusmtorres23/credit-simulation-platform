from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.database import create_database_engine, create_session_factory
from app.errors import register_exception_handlers
from app.routers.simulation_router import router as simulation_router


def create_app(settings: Settings | None = None) -> FastAPI:
    # The middleware retains this list; populate it once settings load at startup.
    allowed_origins: list[str] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        if settings is None:
            # BaseSettings loads required fields from the environment or .env.
            app_settings = Settings()  # pyright: ignore[reportCallIssue]
        else:
            app_settings = settings
        app.state.settings = app_settings
        allowed_origins[:] = app_settings.allowed_origins
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

    application = FastAPI(lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )
    register_exception_handlers(application)
    application.include_router(simulation_router)
    return application


app = create_app()
