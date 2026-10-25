from datetime import timedelta
from uuid import uuid4

import pytest
from factories import make_session
from sqlalchemy import update

from app.models import Session
from app.repositories.session_repository import SessionRepository

pytestmark = pytest.mark.asyncio


async def test_add_stages_session_without_flushing(db):
    session = make_session()
    SessionRepository(db).add(session)
    assert session in db.new
    assert session.id is None
    await db.flush()
    assert session.id is not None


@pytest.mark.parametrize("lookup", ["hash", "id"])
@pytest.mark.parametrize("offset,found", [(-1, True), (0, False), (1, False)])
async def test_active_lookup_respects_exact_expiration(
    db, saved_session, lookup, offset, found
):
    repo = SessionRepository(db)
    now = saved_session.expires_at + timedelta(microseconds=offset)
    if lookup == "hash":
        result = await repo.find_active_by_token_hash(saved_session.token_hash, now=now)
    else:
        result = await repo.find_active_by_id(saved_session.id, now=now)
    assert (result is saved_session) is found


async def test_unknown_credentials_do_not_match_an_existing_session(db, saved_session):
    repo = SessionRepository(db)
    now = saved_session.created_at
    assert await repo.find_active_by_token_hash(b"x" * 32, now=now) is None
    assert await repo.find_active_by_id(uuid4(), now=now) is None


async def test_revalidation_refreshes_previously_loaded_state(db, saved_session):
    session_id = saved_session.id
    original = saved_session.expires_at
    new_expiry = original + timedelta(days=1)
    await db.execute(
        update(Session).where(Session.id == session_id).values(expires_at=new_expiry),
        execution_options={"synchronize_session": False},
    )
    assert saved_session.expires_at == original
    result = await SessionRepository(db).find_active_by_id(
        session_id, now=original, for_update=True
    )
    assert result is saved_session
    assert result.expires_at == new_expiry
