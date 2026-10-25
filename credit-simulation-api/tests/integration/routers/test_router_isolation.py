from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select, update

from app.models import Session

pytestmark = pytest.mark.asyncio


async def test_cookie_isolates_browsers_and_cannot_be_recovered_from_form_data(
    http_stack, http_payload
):
    ctx = http_stack
    created = await ctx.client.post("/api/simulations", json=http_payload)
    record_id = created.json()["id"]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=ctx.app),
        base_url="http://test",
        headers={"Origin": "http://frontend.test"},
    ) as other:
        assert (await other.get("/api/simulations")).json()["total"] == 0
        assert (await other.get(f"/api/simulations/{record_id}")).status_code == 404
        assert (await other.delete(f"/api/simulations/{record_id}")).status_code == 404
        assert (
            await other.post("/api/simulations", json=http_payload)
        ).status_code == 201
        assert other.cookies.get("credit_session") != ctx.client.cookies.get(
            "credit_session"
        )
        assert (await other.get(f"/api/simulations/{record_id}")).status_code == 404
    assert (await ctx.client.get("/api/simulations")).json()["total"] == 1


async def test_expired_server_session_blocks_cookie_and_creation_replaces_it(
    http_stack, http_payload
):
    ctx = http_stack
    created = await ctx.client.post("/api/simulations", json=http_payload)
    old_cookie = ctx.client.cookies.get("credit_session")
    record_id = created.json()["id"]
    async with ctx.db.begin():
        owner = await ctx.db.scalar(select(Session))
        await ctx.db.execute(
            update(Session)
            .where(Session.id == owner.id)
            .values(expires_at=owner.created_at + timedelta(microseconds=1))
        )
    history = await ctx.client.get("/api/simulations")
    assert history.json()["total"] == 0
    assert "set-cookie" not in history.headers
    assert (await ctx.client.get(f"/api/simulations/{record_id}")).status_code == 404
    replacement = await ctx.client.post("/api/simulations", json=http_payload)
    assert replacement.status_code == 201
    assert ctx.client.cookies.get("credit_session") != old_cookie
    assert (await ctx.client.get("/api/simulations")).json()["total"] == 1
