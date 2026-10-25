from types import SimpleNamespace

import httpx
import pytest_asyncio
from pydantic import HttpUrl

from app.database import create_session_factory
from app.dependencies import get_db_session, get_http_client
from app.main import create_app


@pytest_asyncio.fixture
async def real_http_stack(engine, migrated_database, service_clock):
    settings = migrated_database.model_copy(
        update={
            "allowed_origins": ["http://frontend.test"],
            "bank_a_base_url": HttpUrl("http://bank-a.test"),
            "bank_b_base_url": HttpUrl("http://bank-b.test"),
            "session_cookie_secure": False,
        }
    )

    def bank_handler(request):
        if request.url.host == "bank-a.test":
            return httpx.Response(
                200,
                json={
                    "approved": True,
                    "offer": {
                        "amountCents": 100000,
                        "termMonths": 12,
                        "monthlyInterestRateBps": 180,
                        "installmentCents": 9340,
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "decision": {
                    "code": "ACCEPTED",
                    "conditions": {
                        "principal_cents": 100000,
                        "installments": 12,
                        "monthly_rate_bps": 210,
                        "payment_cents": 9514,
                    },
                }
            },
        )

    app = create_app(settings)
    factory = create_session_factory(engine)

    async def override_db():
        async with factory() as db:
            yield db

    async with httpx.AsyncClient(transport=httpx.MockTransport(bank_handler)) as banks:

        async def override_http():
            return banks

        app.dependency_overrides[get_db_session] = override_db
        app.dependency_overrides[get_http_client] = override_http
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                headers={"Origin": "http://frontend.test"},
            ) as client,
        ):
            yield SimpleNamespace(
                app=app, client=client, clock=service_clock, engine=engine
            )
    app.dependency_overrides.clear()
