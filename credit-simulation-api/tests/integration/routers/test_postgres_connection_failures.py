import socket
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from app.config import Settings
from app.dependencies import get_http_client
from app.main import create_app

pytestmark = pytest.mark.asyncio


@pytest.fixture
def refused_database_settings(settings_data):
    socket_handle = socket.socket()
    socket_handle.bind(("127.0.0.1", 0))
    port = socket_handle.getsockname()[1]
    socket_handle.close()
    return settings_data | {
        "postgres_host": "127.0.0.1",
        "postgres_port": port,
        "allowed_origins": ["http://frontend.test"],
        "bank_a_base_url": "http://bank-a.test",
        "bank_b_base_url": "http://bank-b.test",
        "session_cookie_secure": False,
    }


def bank_handler(request, calls):
    calls.append(request)
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


@pytest_asyncio.fixture
async def refused_database_client(refused_database_settings):
    app = create_app(Settings(_env_file=None, **refused_database_settings))
    calls = []
    transport = httpx.MockTransport(lambda request: bank_handler(request, calls))
    async with httpx.AsyncClient(transport=transport) as banks:

        async def override_http():
            return banks

        app.dependency_overrides[get_http_client] = override_http
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                headers={"Origin": "http://frontend.test"},
            ) as client,
        ):
            yield SimpleNamespace(client=client, app=app, bank_calls=calls)


@pytest.mark.parametrize(
    ("method", "path", "expected_code"),
    [
        ("get", "/api/simulations", "HISTORY_UNAVAILABLE"),
        ("get", f"/api/simulations/{uuid4()}", "HISTORY_UNAVAILABLE"),
        ("delete", f"/api/simulations/{uuid4()}", "SIMULATION_DELETE_FAILED"),
    ],
)
async def test_refused_postgres_returns_controlled_history_errors(
    refused_database_client, method, path, expected_code
):
    response = await getattr(refused_database_client.client, method)(
        path,
        headers={"Cookie": "credit_session=" + "a" * 43},
    )
    body = response.json()

    assert response.status_code == 503
    assert set(body) == {"error"}
    assert body["error"]["code"] == expected_code
    assert body["error"]["message"] in {
        "Não foi possível consultar o histórico. Tente novamente mais tarde.",
        "Não foi possível excluir a simulação. Tente novamente mais tarde.",
    }
    assert "ConnectionRefusedError" not in response.text


async def test_refused_postgres_during_creation_returns_no_success_or_cookie(
    refused_database_client, http_payload
):
    response = await refused_database_client.client.post(
        "/api/simulations", json=http_payload
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SIMULATION_SAVE_FAILED"
    assert set(response.json()) == {"error"}
    assert "set-cookie" not in response.headers
    assert len(refused_database_client.bank_calls) == 2


async def test_refused_postgres_during_initial_lookup_skips_banks(
    refused_database_client, http_payload
):
    response = await refused_database_client.client.post(
        "/api/simulations",
        json=http_payload,
        headers={"Cookie": "credit_session=" + "a" * 43},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "SIMULATION_SAVE_FAILED",
            "message": "Não foi possível salvar a simulação. Tente novamente mais tarde.",
        }
    }
    assert "set-cookie" not in response.headers
    assert len(refused_database_client.bank_calls) == 0
