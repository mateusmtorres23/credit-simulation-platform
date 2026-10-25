import pytest

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "patch",
    [
        {"requested_amount_cents": 99},
        {"monthly_income_cents": "private-value"},
        {"cpf": "private-document"},
        {"private-extra-key": "private-extra-value"},
        {"term_months": True},
        {"name": "   "},
    ],
)
async def test_invalid_body_never_calls_service_or_sets_cookie(
    router_context, router_payload, patch
):
    ctx = router_context
    response = await ctx.client.post("/api/simulations", json=router_payload | patch)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "private-" not in response.text
    assert "set-cookie" not in response.headers
    ctx.service.create.assert_not_awaited()


@pytest.mark.parametrize(
    "query", ["bank_a_scenario=unknown", "private-extra-key=value"]
)
async def test_invalid_scenario_query_never_calls_service(
    router_context, router_payload, query
):
    response = await router_context.client.post(
        f"/api/simulations?{query}", json=router_payload
    )
    assert response.status_code == 422
    assert "private-extra-key" not in response.text
    router_context.service.create.assert_not_awaited()


@pytest.mark.parametrize(
    "query", ["page=0", "page_size=51", "page=wrong", "extra=value"]
)
async def test_history_query_validation_prevents_service_call(router_context, query):
    response = await router_context.client.get(f"/api/simulations?{query}")
    assert response.status_code == 422
    router_context.service.list_history.assert_not_awaited()


@pytest.mark.parametrize("method", ["GET", "DELETE"])
async def test_invalid_uuid_returns_sanitized_validation_error(router_context, method):
    response = await router_context.client.request(
        method, "/api/simulations/private-invalid-id"
    )
    assert response.status_code == 422
    assert "private-invalid-id" not in response.text
    router_context.service.get_detail.assert_not_awaited()
    router_context.service.delete.assert_not_awaited()


async def test_missing_body_and_malformed_json_are_rejected(router_context):
    for body in (b"", b'{"name":"private-value",'):
        response = await router_context.client.post(
            "/api/simulations",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422
        assert "private-value" not in response.text
    router_context.service.create.assert_not_awaited()
