from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from pydantic import HttpUrl

from app.dependencies import get_db_session, get_http_client
from app.main import create_app


@pytest.fixture
def http_payload():
    return {
        "name": "Cliente Fictício",
        "email": "cliente@example.com",
        "cpf": "00000000000",
        "employer_cnpj": "00000000000000",
        "monthly_income_cents": 300000,
        "requested_amount_cents": 100000,
        "term_months": 12,
    }


@pytest_asyncio.fixture
async def http_stack(db, migrated_database):
    settings = migrated_database.model_copy(
        update={
            "allowed_origins": ["http://frontend.test"],
            "bank_a_base_url": HttpUrl("http://bank-a.test"),
            "bank_b_base_url": HttpUrl("http://bank-b.test"),
            "session_cookie_secure": False,
        }
    )
    calls = []

    def bank_handler(request):
        calls.append(request)
        if request.url.path.endswith("/unavailable"):
            return httpx.Response(503, content=b"private-upstream-error")
        if request.url.path.endswith("/slow"):
            raise httpx.ReadTimeout("private-timeout", request=request)
        if request.url.host == settings.bank_a_base_url.host:
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
    async with httpx.AsyncClient(transport=httpx.MockTransport(bank_handler)) as banks:

        async def override_db():
            yield db

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
            yield SimpleNamespace(app=app, client=client, calls=calls, db=db)
