from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import dependencies
from app.config import Settings
from app.dependencies import SessionTokenDependency, SimulationServiceDependency
from app.main import create_app

pytestmark = pytest.mark.asyncio


async def test_forbidden_origin_prevents_database_dependency_and_service_execution(
    security_settings,
):
    app = create_app(security_settings)

    async def forbidden_db():
        pytest.fail("Origin must be checked before acquiring a database session")
        yield

    app.dependency_overrides[dependencies.get_db_session] = forbidden_db

    @app.post("/service")
    async def route(service: SimulationServiceDependency):
        pytest.fail("Forbidden request must not reach endpoint")

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post("/service")
    assert response.status_code == 403


async def test_composition_shares_session_client_and_settings(
    monkeypatch, security_settings
):
    service_type = dependencies.SimulationService
    names = [
        "SessionRepository",
        "SimulationRepository",
        "SessionService",
        "SimulationHistoryService",
        "SimulationService",
        "BankAAdapter",
        "BankBAdapter",
    ]
    constructors = {}
    for name in names:
        constructor = Mock(wraps=getattr(dependencies, name))
        monkeypatch.setattr(dependencies, name, constructor)
        constructors[name] = constructor
    app = create_app(security_settings)

    @app.post("/service")
    async def route(
        service: SimulationServiceDependency, token: SessionTokenDependency
    ):
        assert isinstance(service, service_type)
        return {"token": token}

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post(
            "/service",
            headers={
                "Origin": "http://localhost:5173",
                "Cookie": "credit_session=test-credential",
            },
        )
        assert response.status_code == 200
        assert response.json() == {"token": "test-credential"}
        db = constructors["SimulationRepository"].call_args.args[0]
        assert isinstance(db, AsyncSession)
        assert constructors["SessionRepository"].call_args.args[0] is db
        assert constructors["SimulationHistoryService"].call_args.args[0] is db
        assert constructors["SimulationService"].call_args.args[0] is db
        for name, url in [
            ("BankAAdapter", security_settings.bank_a_base_url),
            ("BankBAdapter", security_settings.bank_b_base_url),
        ]:
            constructors[name].assert_called_once_with(
                app.state.http_client, url, security_settings.bank_timeout_seconds
            )


async def test_empty_allowlist_denies_all_writes(settings_data):
    app = create_app(Settings(_env_file=None, **settings_data))

    @app.post("/service")
    async def route(service: SimulationServiceDependency):
        pytest.fail("No origin is allowed by default")

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post(
            "/service", headers={"Origin": "http://localhost:5173"}
        )
    assert response.status_code == 403
