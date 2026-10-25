from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import cleanup

pytestmark = pytest.mark.asyncio


async def test_cleanup_normalizes_cutoff_and_commits_after_repository(monkeypatch):
    now = datetime(2026, 10, 25, tzinfo=timezone(timedelta(hours=-3)))
    repository = Mock()
    repository.delete_expired = AsyncMock(return_value=2)
    monkeypatch.setattr(cleanup, "SessionRepository", lambda db: repository)
    async with AsyncSession() as db:
        assert await cleanup.cleanup_expired_sessions(db, now=now) == 2
        assert not db.in_transaction()
    repository.delete_expired.assert_awaited_once_with(now=now.astimezone(UTC))


async def test_naive_cutoff_fails_before_starting_transaction():
    async with AsyncSession() as db:
        with pytest.raises(ValueError, match="timezone"):
            await cleanup.cleanup_expired_sessions(db, now=datetime(2026, 10, 25))
        assert not db.in_transaction()


@pytest.mark.parametrize("fails", [False, True])
async def test_run_cleanup_disposes_engine_on_success_or_failure(monkeypatch, fails):
    engine = Mock()
    engine.dispose = AsyncMock()
    monkeypatch.setattr(cleanup, "create_database_engine", lambda settings: engine)
    monkeypatch.setattr(cleanup, "create_session_factory", lambda engine: AsyncSession)
    operation = AsyncMock(return_value=4)
    failure = RuntimeError("forced failure")
    if fails:
        operation.side_effect = failure
    monkeypatch.setattr(cleanup, "cleanup_expired_sessions", operation)
    if fails:
        with pytest.raises(RuntimeError) as error:
            await cleanup.run_cleanup(object())
        assert error.value is failure
    else:
        assert await cleanup.run_cleanup(object()) == 4
    engine.dispose.assert_awaited_once_with()
