import asyncio
import hashlib
from contextlib import suppress
from datetime import timedelta

import pytest
from session_lock_support import (
    backend_pid,
    locked_session,
    observe_lock_request,
    wait_for_blocking,
)
from sqlalchemy import delete, event, select

from app.database import create_session_factory
from app.errors import SimulationNotFound
from app.models import Session, Simulation

pytestmark = pytest.mark.asyncio


async def test_creation_rechecks_expiration_after_real_lock_wait(
    build_service, engine, service_clock
):
    first_session_id = replacement_session_id = None
    operation = None
    async with create_session_factory(engine)() as operation_db:
        try:
            ctx = build_service(operation_db)
            first = await ctx.service.create(ctx.request, ctx.scenarios, None)
            first_session_id = await operation_db.scalar(
                select(Session.id).where(
                    Session.token_hash
                    == hashlib.sha256(first.new_token.encode()).digest()
                )
            )
            await operation_db.rollback()
            original_expiry = first.session_expires_at
            async with locked_session(
                engine, first_session_id, service_clock.now
            ) as locker:
                locker_pid = await backend_pid(locker)
                requested, target, listener = observe_lock_request(operation_db)
                try:
                    operation = asyncio.create_task(
                        ctx.service.create(ctx.request, ctx.scenarios, first.new_token)
                    )
                    await asyncio.wait_for(requested.wait(), timeout=5)
                    operation_pid = await wait_for_blocking(engine, locker_pid)
                    assert operation_pid != locker_pid
                    assert not operation.done()
                    service_clock.now = original_expiry
                finally:
                    event.remove(target, "before_cursor_execute", listener)
            replacement = await asyncio.wait_for(operation, timeout=5)
            assert replacement.new_token != first.new_token
            assert replacement.session_expires_at == service_clock.now + timedelta(
                days=7
            )
            assert replacement.response.created_at == service_clock.now
            replacement_session_id = await operation_db.scalar(
                select(Session.id).where(
                    Session.token_hash
                    == hashlib.sha256(replacement.new_token.encode()).digest()
                )
            )
            await operation_db.rollback()
            assert (
                await ctx.service.get_detail(
                    replacement.response.id, replacement.new_token
                )
            ).id == replacement.response.id
            async with engine.connect() as reader:
                old = (
                    await reader.execute(
                        select(Session.created_at, Session.expires_at).where(
                            Session.id == first_session_id
                        )
                    )
                ).one()
                saved = (
                    await reader.execute(
                        select(Simulation.session_id, Simulation.created_at).where(
                            Simulation.id == replacement.response.id
                        )
                    )
                ).one()
                assert old[0] < old[1] == original_expiry
                assert saved[0] == replacement_session_id
                assert saved[1] == replacement.response.created_at
        finally:
            if operation is not None and not operation.done():
                operation.cancel()
                with suppress(asyncio.CancelledError):
                    await operation
            async with engine.begin() as cleanup:
                ids = [
                    value
                    for value in (first_session_id, replacement_session_id)
                    if value
                ]
                if ids:
                    await cleanup.execute(delete(Session).where(Session.id.in_(ids)))


async def test_delete_rechecks_expiration_after_real_lock_wait(
    build_service, engine, service_clock
):
    session_id = None
    operation = None
    async with create_session_factory(engine)() as operation_db:
        try:
            ctx = build_service(operation_db)
            created = await ctx.service.create(ctx.request, ctx.scenarios, None)
            session_id = await operation_db.scalar(
                select(Session.id).where(
                    Session.token_hash
                    == hashlib.sha256(created.new_token.encode()).digest()
                )
            )
            await operation_db.rollback()
            async with locked_session(engine, session_id, service_clock.now) as locker:
                locker_pid = await backend_pid(locker)
                requested, target, listener = observe_lock_request(operation_db)
                try:
                    operation = asyncio.create_task(
                        ctx.service.delete(created.response.id, created.new_token)
                    )
                    await asyncio.wait_for(requested.wait(), timeout=5)
                    operation_pid = await wait_for_blocking(engine, locker_pid)
                    assert operation_pid != locker_pid
                    assert not operation.done()
                    service_clock.now = created.session_expires_at
                finally:
                    event.remove(target, "before_cursor_execute", listener)
            with pytest.raises(SimulationNotFound):
                await asyncio.wait_for(operation, timeout=5)
            async with engine.connect() as reader:
                assert (
                    await reader.scalar(
                        select(Simulation.id).where(
                            Simulation.id == created.response.id
                        )
                    )
                    == created.response.id
                )
        finally:
            if operation is not None and not operation.done():
                operation.cancel()
                with suppress(asyncio.CancelledError):
                    await operation
            async with engine.begin() as cleanup:
                if session_id is not None:
                    await cleanup.execute(
                        delete(Session).where(Session.id == session_id)
                    )
