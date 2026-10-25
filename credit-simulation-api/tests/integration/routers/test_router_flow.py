import pytest
from sqlalchemy import func, select

from app.models import BankResult, Session, Simulation

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "query,statuses",
    [
        ("", ["approved", "approved"]),
        ("?bank_b_scenario=unavailable", ["approved", "failed"]),
        ("?bank_a_scenario=slow&bank_b_scenario=unavailable", ["failed", "failed"]),
    ],
)
async def test_http_database_and_adapters_roundtrip(
    http_stack, http_payload, query, statuses
):
    ctx = http_stack
    created = await ctx.client.post(f"/api/simulations{query}", json=http_payload)
    assert created.status_code == 201
    assert [result["status"] for result in created.json()["results"]] == statuses
    assert "private-" not in created.text
    token = ctx.client.cookies.get("credit_session")
    assert token
    record_id = created.json()["id"]
    history = await ctx.client.get("/api/simulations")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["id"] == record_id
    detail = await ctx.client.get(f"/api/simulations/{record_id}")
    assert detail.status_code == 200
    assert detail.json()["results"] == created.json()["results"]
    assert set(detail.json()["request"]) == {
        "monthly_income_cents",
        "requested_amount_cents",
        "term_months",
    }
    second = await ctx.client.post("/api/simulations", json=http_payload)
    assert second.status_code == 201
    assert "set-cookie" not in second.headers
    assert ctx.client.cookies.get("credit_session") == token
    removed = await ctx.client.delete(f"/api/simulations/{record_id}")
    assert removed.status_code == 204 and removed.content == b""
    for response in (history, detail, removed):
        assert "set-cookie" not in response.headers
    assert (await ctx.client.get(f"/api/simulations/{record_id}")).status_code == 404
    assert (await ctx.client.get("/api/simulations")).json()["total"] == 1
    assert len(ctx.calls) == 4
    async with ctx.db.begin():
        assert await ctx.db.scalar(select(func.count()).select_from(Session)) == 1
        assert await ctx.db.scalar(select(func.count()).select_from(Simulation)) == 1
        assert await ctx.db.scalar(select(func.count()).select_from(BankResult)) == 2


async def test_missing_cookie_history_does_not_create_session_or_call_banks(http_stack):
    response = await http_stack.client.get("/api/simulations?page=4&page_size=2")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 4, "page_size": 2}
    assert "set-cookie" not in response.headers
    assert not http_stack.calls
    async with http_stack.db.begin():
        assert (
            await http_stack.db.scalar(select(func.count()).select_from(Session)) == 0
        )
