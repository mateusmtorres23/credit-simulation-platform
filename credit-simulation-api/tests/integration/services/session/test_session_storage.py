import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import Session
from app.repositories.session_repository import SessionRepository
from app.services.session_service import SessionService

pytestmark = pytest.mark.asyncio


async def test_session_credential_roundtrip_and_expiration_boundary(db, service_clock):
    service = SessionService(SessionRepository(db))
    now = service_clock.now
    async with db.begin():
        prepared = await service.prepare_for_simulation(None, now=now)
        token = prepared.new_token
    async with db.begin():
        stored = await service.find_active(token, now=now)
        assert stored.id == prepared.session.id
        assert stored.token_hash == hashlib.sha256(token.encode()).digest()
        assert await service.find_active(stored.token_hash.hex(), now=now) is None
        assert await service.find_active(token, now=now + timedelta(days=7)) is None
        assert (
            await service.find_active(
                token, now=now + timedelta(days=7, microseconds=-1)
            )
            is stored
        )


async def test_expired_session_is_replaced_without_modifying_previous_dates(
    db, service_clock
):
    service = SessionService(SessionRepository(db))
    now = service_clock.now
    async with db.begin():
        first = await service.prepare_for_simulation(None, now=now)
    async with db.begin():
        replacement = await service.prepare_for_simulation(
            first.session.id, now=now + timedelta(days=7)
        )
    assert replacement.session.id != first.session.id
    assert replacement.new_token != first.new_token
    assert first.session.created_at == now
    assert first.session.expires_at == now + timedelta(days=7)
    assert replacement.session.expires_at == now + timedelta(days=14)
    async with db.begin():
        assert await db.scalar(select(func.count()).select_from(Session)) == 2
