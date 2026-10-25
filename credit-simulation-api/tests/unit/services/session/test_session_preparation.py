import hashlib
import re
from datetime import timedelta
from uuid import uuid4

import pytest
from factories import make_session
from sqlalchemy.exc import SQLAlchemyError

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("previous", [False, True])
async def test_new_or_lost_session_gets_independent_credential(
    session_context, previous
):
    repo, service, now = session_context
    prepared = await service.prepare_for_simulation(
        uuid4() if previous else None, now=now
    )
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", prepared.new_token)
    assert prepared.session.id.version == 4
    assert (
        prepared.session.token_hash
        == hashlib.sha256(prepared.new_token.encode()).digest()
    )
    assert prepared.session.created_at == now
    assert prepared.session.expires_at == now + timedelta(days=7)
    assert prepared.new_token not in repr(prepared)
    assert not hasattr(prepared.session, "token")
    repo.add.assert_called_once_with(prepared.session)
    if previous:
        assert repo.find_active_by_id.await_args.kwargs["for_update"] is True
    else:
        repo.find_active_by_id.assert_not_awaited()


async def test_valid_session_is_reused_without_renewal_or_new_token(session_context):
    repo, service, now = session_context
    existing = make_session(
        id=uuid4(),
        created_at=now - timedelta(days=6),
        expires_at=now + timedelta(days=1),
    )
    repo.find_active_by_id.return_value = existing
    prepared = await service.prepare_for_simulation(existing.id, now=now)
    assert prepared.session is existing
    assert prepared.new_token is None
    assert existing.created_at == now - timedelta(days=6)
    assert existing.expires_at == now + timedelta(days=1)
    repo.add.assert_not_called()


async def test_new_credentials_are_distinct(session_context):
    _, service, now = session_context
    first = await service.prepare_for_simulation(None, now=now)
    second = await service.prepare_for_simulation(None, now=now)
    assert first.new_token != second.new_token
    assert first.session.id != second.session.id
    assert first.session.token_hash != second.session.token_hash


async def test_repository_failure_is_not_treated_as_missing_session(session_context):
    repo, service, now = session_context
    failure = SQLAlchemyError("database unavailable")
    repo.find_active_by_id.side_effect = failure
    with pytest.raises(SQLAlchemyError) as error:
        await service.prepare_for_simulation(uuid4(), now=now)
    assert error.value is failure
    repo.add.assert_not_called()
