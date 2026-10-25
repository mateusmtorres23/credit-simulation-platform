from uuid import uuid4

import pytest

from app.errors import (
    HistoryUnavailable,
    SimulationDeleteFailed,
    SimulationNotFound,
    SimulationSaveFailed,
)

pytestmark = pytest.mark.asyncio


async def test_history_and_detail_forward_validated_parameters_without_setting_cookie(
    router_context,
):
    ctx = router_context
    response = await ctx.client.get("/api/simulations?page=2&page_size=3")
    assert response.status_code == 200
    token, pagination = ctx.service.list_history.await_args.args
    assert token is None
    assert pagination.page == 2 and pagination.page_size == 3
    assert "set-cookie" not in response.headers
    record_id = ctx.result.id
    response = await ctx.client.get(f"/api/simulations/{record_id}")
    assert response.status_code == 200
    ctx.service.get_detail.assert_awaited_once_with(record_id, None)
    assert "set-cookie" not in response.headers


async def test_delete_returns_204_without_body_and_preserves_cookie(router_context):
    ctx = router_context
    record_id = uuid4()
    response = await ctx.client.delete(
        f"/api/simulations/{record_id}", headers={"Cookie": "credit_session=existing"}
    )
    assert response.status_code == 204
    assert response.content == b""
    assert "set-cookie" not in response.headers
    ctx.service.delete.assert_awaited_once_with(record_id, "existing")


@pytest.mark.parametrize(
    "method,path,operation,error,status",
    [
        ("POST", "/api/simulations", "create", SimulationSaveFailed, 503),
        ("GET", "/api/simulations", "list_history", HistoryUnavailable, 503),
        ("GET", "/api/simulations/{id}", "get_detail", SimulationNotFound, 404),
        ("GET", "/api/simulations/{id}", "get_detail", HistoryUnavailable, 503),
        ("DELETE", "/api/simulations/{id}", "delete", SimulationNotFound, 404),
        ("DELETE", "/api/simulations/{id}", "delete", SimulationDeleteFailed, 503),
    ],
)
async def test_service_errors_use_registered_envelope_without_cookie(
    router_context, router_payload, method, path, operation, error, status
):
    ctx = router_context
    getattr(ctx.service, operation).side_effect = error()
    response = await ctx.client.request(
        method,
        path.format(id=uuid4()),
        json=router_payload if method == "POST" else None,
    )
    assert response.status_code == status
    assert response.json() == {"error": {"code": error.code, "message": error.message}}
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("method", ["POST", "DELETE"])
async def test_router_rejects_forbidden_origin(router_context, router_payload, method):
    path = "/api/simulations" if method == "POST" else f"/api/simulations/{uuid4()}"
    response = await router_context.client.request(
        method,
        path,
        json=router_payload if method == "POST" else None,
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "REQUEST_FORBIDDEN"
    router_context.service.create.assert_not_awaited()
    router_context.service.delete.assert_not_awaited()


async def test_openapi_declares_public_contracts_and_empty_delete_response(
    router_context,
):
    schema = router_context.app.openapi()
    paths = schema["paths"]
    assert set(paths["/api/simulations"]) == {"get", "post"}
    assert set(paths["/api/simulations/{simulation_id}"]) == {"get", "delete"}
    assert (
        "content"
        not in paths["/api/simulations/{simulation_id}"]["delete"]["responses"]["204"]
    )
    assert paths["/api/simulations"]["post"]["responses"]["201"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("SimulationCreatedResponse")
