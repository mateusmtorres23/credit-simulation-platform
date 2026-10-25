from collections.abc import AsyncGenerator
from typing import Annotated, cast

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def get_http_client(request: Request) -> httpx.AsyncClient:
    return cast(httpx.AsyncClient, request.app.state.http_client)


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession]:
    session_factory = cast(
        async_sessionmaker[AsyncSession], request.app.state.session_factory
    )
    async with session_factory() as session:
        yield session


HttpClientDependency = Annotated[httpx.AsyncClient, Depends(get_http_client)]
DatabaseSessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
