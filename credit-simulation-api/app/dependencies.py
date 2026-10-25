from collections.abc import AsyncGenerator
from typing import Annotated, cast

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.errors import RequestForbidden
from app.integrations.bank_a import BankAAdapter
from app.integrations.bank_b import BankBAdapter
from app.repositories.session_repository import SessionRepository
from app.repositories.simulation_repository import SimulationRepository
from app.services.session_service import SessionService
from app.services.simulation_history_service import SimulationHistoryService
from app.services.simulation_service import SimulationService

SESSION_COOKIE_NAME = "credit_session"


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_session_token(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE_NAME)


def require_trusted_origin(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    if request.method not in {"POST", "DELETE"}:
        return
    origins = request.headers.getlist("origin")
    if len(origins) != 1 or origins[0] not in settings.allowed_origins:
        raise RequestForbidden()


def get_http_client(request: Request) -> httpx.AsyncClient:
    return cast(httpx.AsyncClient, request.app.state.http_client)


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession]:
    session_factory = cast(
        async_sessionmaker[AsyncSession], request.app.state.session_factory
    )
    async with session_factory() as session:
        yield session


def get_simulation_service(
    trusted_origin: Annotated[None, Depends(require_trusted_origin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SimulationService:
    repository = SimulationRepository(db)
    sessions = SessionService(SessionRepository(db))
    history = SimulationHistoryService(db, repository, sessions)
    return SimulationService(
        db,
        repository,
        sessions,
        BankAAdapter(client, settings.bank_a_base_url, settings.bank_timeout_seconds),
        BankBAdapter(client, settings.bank_b_base_url, settings.bank_timeout_seconds),
        history,
    )


HttpClientDependency = Annotated[httpx.AsyncClient, Depends(get_http_client)]
DatabaseSessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
SessionTokenDependency = Annotated[str | None, Depends(get_session_token)]
SimulationServiceDependency = Annotated[
    SimulationService, Depends(get_simulation_service)
]
