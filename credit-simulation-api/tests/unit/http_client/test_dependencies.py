import httpx
import pytest

from app.dependencies import HttpClientDependency, get_http_client
from app.main import create_app


@pytest.mark.asyncio
async def test_dependency_reuses_client_across_requests_without_closing_it(
    http_settings,
):
    app = create_app(http_settings)
    received = []

    @app.get("/client")
    async def client_route(client: HttpClientDependency):
        received.append(client)
        return {"closed": client.is_closed}

    async with app.router.lifespan_context(app):
        shared = app.state.http_client
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as caller:
            for _ in range(2):
                response = await caller.get("/client")
                assert response.status_code == 200
                assert response.json() == {"closed": False}
        assert len(received) == 2
        assert all(client is shared for client in received)
        assert not shared.is_closed
    assert shared.is_closed


@pytest.mark.asyncio
async def test_dependency_can_be_overridden_with_controlled_client(http_settings):
    app = create_app(http_settings)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"bank": "mock"})
    )
    async with httpx.AsyncClient(transport=transport) as substitute:
        app.dependency_overrides[get_http_client] = lambda: substitute

        @app.get("/bank")
        async def bank_route(client: HttpClientDependency):
            assert client is substitute
            response = await client.get("https://bank.example/evaluations/normal")
            return response.json()

        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as caller,
        ):
            response = await caller.get("/bank")
            assert response.status_code == 200
            assert response.json() == {"bank": "mock"}
        assert not substitute.is_closed
    assert substitute.is_closed
