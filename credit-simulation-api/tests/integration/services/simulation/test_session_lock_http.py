import asyncio
from contextlib import suppress
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx
import pytest
from session_lock_support import (
    backend_pid,
    http_payload,
    locked_session,
    locked_simulations,
    session_by_token,
    wait_for_blocking,
)
from sqlalchemy import delete, select

from app.models import Session, Simulation

pytestmark = pytest.mark.asyncio


async def test_http_creation_rechecks_expiration_after_real_lock_wait(real_http_stack):
    ctx = real_http_stack
    old_session_id = replacement_session_id = None
    operation = None
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=ctx.app),
        base_url="http://test",
        headers={"Origin": "http://frontend.test"},
    ) as old_client:
        try:
            created = await ctx.client.post("/api/simulations", json=http_payload())
            assert created.status_code == 201
            old_token = ctx.client.cookies.get("credit_session")
            assert old_token
            old_session = await session_by_token(ctx.engine, old_token)
            old_session_id = old_session[0]
            async with locked_session(
                ctx.engine, old_session_id, ctx.clock.now
            ) as locker:
                locker_pid = await backend_pid(locker)
                operation = asyncio.create_task(
                    ctx.client.post("/api/simulations", json=http_payload())
                )
                operation_pid = await wait_for_blocking(ctx.engine, locker_pid)
                assert operation_pid != locker_pid
                assert not operation.done()
                ctx.clock.now = old_session[3]
            response = await asyncio.wait_for(operation, timeout=5)
            assert response.status_code == 201
            new_token = ctx.client.cookies.get("credit_session")
            assert new_token and new_token != old_token
            cookie_expiry = parsedate_to_datetime(
                response.headers["set-cookie"].split("expires=", 1)[1].split(";", 1)[0]
            )
            new_session = await session_by_token(ctx.engine, new_token)
            replacement_session_id = new_session[0]
            assert int(cookie_expiry.timestamp()) == int(new_session[3].timestamp())
            assert new_session[2] == ctx.clock.now
            assert new_session[3] == ctx.clock.now + timedelta(days=7)
            assert (
                datetime.fromisoformat(response.json()["created_at"]) == ctx.clock.now
            )
            record_id = response.json()["id"]
            async with ctx.engine.connect() as reader:
                saved = (
                    await reader.execute(
                        select(Simulation.session_id, Simulation.created_at).where(
                            Simulation.id == record_id
                        )
                    )
                ).one()
                assert saved == (replacement_session_id, ctx.clock.now)
            assert (
                await ctx.client.get(f"/api/simulations/{record_id}")
            ).status_code == 200
            old_client.cookies.set("credit_session", old_token)
            assert (
                await old_client.get(f"/api/simulations/{record_id}")
            ).status_code == 404
            assert old_session[3] == ctx.clock.now
        finally:
            if operation is not None and not operation.done():
                operation.cancel()
                with suppress(asyncio.CancelledError):
                    await operation
            async with ctx.engine.begin() as cleanup:
                ids = [
                    value for value in (old_session_id, replacement_session_id) if value
                ]
                if ids:
                    await cleanup.execute(delete(Session).where(Session.id.in_(ids)))


async def test_http_delete_rechecks_expiration_after_real_lock_wait(real_http_stack):
    ctx = real_http_stack
    session_id = None
    operation = None
    try:
        created = await ctx.client.post("/api/simulations", json=http_payload())
        assert created.status_code == 201
        token = ctx.client.cookies.get("credit_session")
        assert token
        session = await session_by_token(ctx.engine, token)
        session_id = session[0]
        record_id = created.json()["id"]
        async with locked_session(ctx.engine, session_id, ctx.clock.now) as locker:
            locker_pid = await backend_pid(locker)
            operation = asyncio.create_task(
                ctx.client.delete(f"/api/simulations/{record_id}")
            )
            operation_pid = await wait_for_blocking(ctx.engine, locker_pid)
            assert operation_pid != locker_pid
            assert not operation.done()
            ctx.clock.now = session[3]
        response = await asyncio.wait_for(operation, timeout=5)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SIMULATION_NOT_FOUND"
        assert "set-cookie" not in response.headers
        async with ctx.engine.connect() as reader:
            assert (
                str(
                    await reader.scalar(
                        select(Simulation.id).where(Simulation.id == record_id)
                    )
                )
                == record_id
            )
    finally:
        if operation is not None and not operation.done():
            operation.cancel()
            with suppress(asyncio.CancelledError):
                await operation
        async with ctx.engine.begin() as cleanup:
            if session_id is not None:
                await cleanup.execute(delete(Session).where(Session.id == session_id))


async def test_http_history_rechecks_expiration_after_real_read_lock_wait(
    real_http_stack,
):
    ctx = real_http_stack
    session_id = None
    operation = None
    try:
        created = await ctx.client.post("/api/simulations", json=http_payload())
        assert created.status_code == 201
        token = ctx.client.cookies.get("credit_session")
        assert token
        session = await session_by_token(ctx.engine, token)
        session_id = session[0]
        async with locked_simulations(ctx.engine) as locker:
            locker_pid = await backend_pid(locker)
            operation = asyncio.create_task(
                ctx.client.get(
                    "/api/simulations?page=3&page_size=2",
                    headers={"Cookie": f"credit_session={token}"},
                )
            )
            operation_pid = await wait_for_blocking(
                ctx.engine, locker_pid, query_fragment="simulations"
            )
            assert operation_pid != locker_pid
            assert not operation.done()
            ctx.clock.now = session[3]
        response = await asyncio.wait_for(operation, timeout=5)
        assert response.status_code == 200
        assert response.json() == {
            "items": [],
            "total": 0,
            "page": 3,
            "page_size": 2,
        }
        assert "set-cookie" not in response.headers
    finally:
        if operation is not None and not operation.done():
            operation.cancel()
            with suppress(asyncio.CancelledError):
                await operation
        async with ctx.engine.begin() as cleanup:
            if session_id is not None:
                await cleanup.execute(delete(Session).where(Session.id == session_id))


async def test_http_detail_rechecks_expiration_after_real_read_lock_wait(
    real_http_stack,
):
    ctx = real_http_stack
    session_id = None
    operation = None
    try:
        created = await ctx.client.post("/api/simulations", json=http_payload())
        assert created.status_code == 201
        token = ctx.client.cookies.get("credit_session")
        assert token
        session = await session_by_token(ctx.engine, token)
        session_id = session[0]
        simulation_id = created.json()["id"]
        async with locked_simulations(ctx.engine) as locker:
            locker_pid = await backend_pid(locker)
            operation = asyncio.create_task(
                ctx.client.get(
                    f"/api/simulations/{simulation_id}",
                    headers={"Cookie": f"credit_session={token}"},
                )
            )
            operation_pid = await wait_for_blocking(
                ctx.engine, locker_pid, query_fragment="simulations"
            )
            assert operation_pid != locker_pid
            assert not operation.done()
            ctx.clock.now = session[3]
        response = await asyncio.wait_for(operation, timeout=5)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SIMULATION_NOT_FOUND"
        assert "set-cookie" not in response.headers
    finally:
        if operation is not None and not operation.done():
            operation.cancel()
            with suppress(asyncio.CancelledError):
                await operation
        async with ctx.engine.begin() as cleanup:
            if session_id is not None:
                await cleanup.execute(delete(Session).where(Session.id == session_id))
