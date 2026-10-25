from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.models import BankResult, Session, Simulation

pytestmark = pytest.mark.asyncio


async def test_save_failure_never_publishes_cookie_or_bank_results(
    http_stack, http_payload, monkeypatch
):
    ctx = http_stack
    monkeypatch.setattr(
        ctx.db, "flush", AsyncMock(side_effect=SQLAlchemyError("private-db-error"))
    )
    response = await ctx.client.post("/api/simulations", json=http_payload)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SIMULATION_SAVE_FAILED"
    assert set(response.json()) == {"error"}
    assert "private-" not in response.text
    assert "set-cookie" not in response.headers
    async with ctx.db.begin():
        for model in (Session, Simulation, BankResult):
            assert await ctx.db.scalar(select(func.count()).select_from(model)) == 0


async def test_invalid_input_and_forbidden_origin_never_call_banks(
    http_stack, http_payload
):
    ctx = http_stack
    invalid = await ctx.client.post(
        "/api/simulations", json=http_payload | {"term_months": 0}
    )
    assert invalid.status_code == 422
    forbidden = await ctx.client.post(
        "/api/simulations", json=http_payload, headers={"Origin": "https://evil.test"}
    )
    assert forbidden.status_code == 403
    assert not ctx.calls
    async with ctx.db.begin():
        assert await ctx.db.scalar(select(func.count()).select_from(Session)) == 0
