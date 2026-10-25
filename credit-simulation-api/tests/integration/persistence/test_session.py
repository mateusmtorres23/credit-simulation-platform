from datetime import timedelta

import pytest
from factories import (
    make_session,
)
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.models import Session

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("size", [31, 33])
async def test_token_hash_requires_32_bytes(db, saved_session, size):
    with pytest.raises(IntegrityError, match="ck_sessions_token_hash_length"):
        async with db.begin_nested():
            await db.execute(
                update(Session)
                .where(Session.id == saved_session.id)
                .values(token_hash=b"x" * size)
            )


async def test_token_hash_is_unique(db, saved_session):
    duplicate = make_session(token_hash=saved_session.token_hash)
    with pytest.raises(IntegrityError, match="uq_sessions_token_hash"):
        async with db.begin_nested():
            db.add(duplicate)
            await db.flush()


@pytest.mark.parametrize("days", [0, -1])
async def test_expiration_must_follow_creation(db, saved_session, days):
    with pytest.raises(IntegrityError, match="ck_sessions_expiration_after_creation"):
        async with db.begin_nested():
            await db.execute(
                update(Session)
                .where(Session.id == saved_session.id)
                .values(expires_at=saved_session.created_at + timedelta(days=days))
            )


async def test_session_dates_round_trip(db, saved_session):
    session_id = saved_session.id
    created_at, expires_at = saved_session.created_at, saved_session.expires_at
    db.expunge_all()
    saved = await db.get(Session, session_id)
    assert saved.created_at == created_at
    assert saved.expires_at == expires_at
    assert saved.created_at.utcoffset() == timedelta(0)
