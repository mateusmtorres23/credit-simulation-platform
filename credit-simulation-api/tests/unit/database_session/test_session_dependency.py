import asyncio

import httpx
import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DatabaseSessionDependency, get_db_session


@pytest.mark.asyncio
async def test_one_session_per_request_is_reused_and_closed_without_commit(
    database_app,
):
    app = database_app.app
    received = []

    @app.get("/session")
    async def route(
        first: DatabaseSessionDependency, second: DatabaseSessionDependency
    ):
        assert first is second
        assert isinstance(first, AsyncSession)
        assert first.bind is app.state.database_engine
        first.close.assert_not_awaited()
        received.append(first)
        return {"ok": True}

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as caller:
            for _ in range(2):
                response = await caller.get("/session")
                assert response.status_code == 200
        assert len(received) == 2
        assert received[0] is not received[1]
        assert database_app.sessions == received
        for session in received:
            session.close.assert_awaited_once_with()
            session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_endpoint_exception_still_closes_session(database_app):
    app = database_app.app
    failure = RuntimeError("endpoint failure")

    @app.get("/failure")
    async def route(session: DatabaseSessionDependency):
        raise failure

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as caller:
            with pytest.raises(RuntimeError) as error:
                await caller.get("/failure")
        assert error.value is failure
        session = database_app.sessions[0]
        session.close.assert_awaited_once_with()
        session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancellation_propagates_and_closes_session(database_app):
    app = database_app.app
    async with app.router.lifespan_context(app):
        dependency = get_db_session(Request({"type": "http", "app": app}))
        session = await anext(dependency)
        with pytest.raises(asyncio.CancelledError):
            await dependency.athrow(asyncio.CancelledError())
        session.close.assert_awaited_once_with()
        session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_dependency_can_be_overridden_without_creating_session(database_app):
    app = database_app.app
    substitute = object()

    async def override():
        yield substitute

    app.dependency_overrides[get_db_session] = override

    @app.get("/override")
    async def route(session: DatabaseSessionDependency):
        return {"overridden": session is substitute}

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as caller:
            response = await caller.get("/override")
        assert response.status_code == 200
        assert response.json() == {"overridden": True}
        assert not database_app.sessions
