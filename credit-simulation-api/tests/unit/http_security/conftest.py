import httpx
import pytest
import pytest_asyncio
from fastapi import Depends

from app.config import Settings
from app.dependencies import require_trusted_origin
from app.main import create_app


@pytest.fixture(autouse=True)
def isolate_http_security_environment(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)


@pytest.fixture
def security_settings(settings_data):
    return Settings(
        _env_file=None, **settings_data, allowed_origins=["http://localhost:5173"]
    )


@pytest_asyncio.fixture
async def security_client(security_settings):
    app = create_app(security_settings)

    @app.api_route(
        "/protected",
        methods=["GET", "POST", "DELETE"],
        dependencies=[Depends(require_trusted_origin)],
    )
    async def protected():
        return {"ok": True}

    @app.get("/validate")
    async def validate(page: int):
        return {"page": page}

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        yield client
