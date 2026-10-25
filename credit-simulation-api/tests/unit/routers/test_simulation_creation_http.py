from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie

import pytest

from app.services.simulation_service import CreatedSimulation

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("secure", [False, True])
async def test_creation_returns_public_response_and_persistent_protected_cookie(
    router_context, router_payload, secure
):
    ctx = router_context
    ctx.settings.session_cookie_secure = secure
    response = await ctx.client.post("/api/simulations", json=router_payload)
    assert response.status_code == 201
    assert response.json() == ctx.result.model_dump(mode="json")
    assert "new_token" not in response.json()
    cookie = SimpleCookie(response.headers["set-cookie"])["credit_session"]
    assert cookie.value == "a" * 43
    assert cookie["httponly"]
    assert bool(cookie["secure"]) is secure
    assert cookie["samesite"] == "lax"
    assert cookie["path"] == "/api"
    assert cookie["domain"] == ""
    assert (
        parsedate_to_datetime(cookie["expires"])
        == ctx.service.create.return_value.session_expires_at
    )
    payload, scenarios, token = ctx.service.create.await_args.args
    assert payload.model_dump() == router_payload
    assert scenarios.model_dump() == {
        "bank_a_scenario": "normal",
        "bank_b_scenario": "normal",
    }
    assert token is None


async def test_creation_passes_scenarios_and_existing_cookie_without_renewing(
    router_context, router_payload
):
    ctx = router_context
    created = ctx.service.create.return_value
    ctx.service.create.return_value = CreatedSimulation(
        created.response, created.session_expires_at
    )
    response = await ctx.client.post(
        "/api/simulations?bank_a_scenario=slow&bank_b_scenario=unavailable",
        json=router_payload,
        headers={"Cookie": "credit_session=existing-credential"},
    )
    assert response.status_code == 201
    assert "set-cookie" not in response.headers
    _, scenarios, token = ctx.service.create.await_args.args
    assert scenarios.bank_a_scenario == "slow"
    assert scenarios.bank_b_scenario == "unavailable"
    assert token == "existing-credential"
