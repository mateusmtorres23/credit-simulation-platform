import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from factories import make_session

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "token", [None, "", "x" * 42, "x" * 44, "é" * 43, " " * 43, "a" * 64]
)
async def test_invalid_credentials_do_not_query_or_create_session(
    session_context, token
):
    repo, service, now = session_context
    assert await service.find_active(token, now=now) is None
    repo.find_active_by_token_hash.assert_not_awaited()
    repo.add.assert_not_called()


async def test_lookup_hashes_exact_credential_and_preserves_existing_dates(
    session_context,
):
    repo, service, now = session_context
    token = "a" * 43
    existing = make_session()
    dates = existing.created_at, existing.expires_at
    repo.find_active_by_token_hash.return_value = existing
    assert await service.find_active(token, now=now) is existing
    repo.find_active_by_token_hash.assert_awaited_once_with(
        hashlib.sha256(token.encode("utf-8")).digest(), now=now
    )
    assert (existing.created_at, existing.expires_at) == dates
    repo.add.assert_not_called()


async def test_revalidation_requests_lock_and_utc_time(session_context):
    repo, service, now = session_context
    local = now.astimezone(timezone(timedelta(hours=-3)))
    session_id = uuid4()
    await service.revalidate_for_write(session_id, now=local)
    repo.find_active_by_id.assert_awaited_once_with(
        session_id, now=now, for_update=True
    )


@pytest.mark.parametrize("operation", ["lookup", "prepare", "revalidate"])
async def test_naive_server_time_is_rejected(session_context, operation):
    repo, service, _ = session_context
    now = datetime(2026, 10, 24)
    with pytest.raises(ValueError, match="timezone"):
        if operation == "lookup":
            await service.find_active("a" * 43, now=now)
        elif operation == "prepare":
            await service.prepare_for_simulation(None, now=now)
        else:
            await service.revalidate_for_write(uuid4(), now=now)
    repo.add.assert_not_called()
