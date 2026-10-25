from datetime import UTC, datetime, timedelta

import pytest
from factories import make_graph
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.cleanup import cleanup_expired_sessions
from app.models import BankResult, BankResultReason, Session, Simulation

pytestmark = pytest.mark.asyncio


async def test_failure_before_commit_restores_sessions_and_all_descendants(db):
    now = datetime.now(UTC)
    graph = make_graph()
    graph.session.created_at = now - timedelta(days=8)
    graph.session.expires_at = now - timedelta(days=1)
    db.add(graph.session)
    await db.commit()
    failure = SQLAlchemyError("forced cleanup commit failure")

    def fail_commit(session):
        raise failure

    event.listen(db.sync_session, "before_commit", fail_commit)
    try:
        with pytest.raises(SQLAlchemyError) as error:
            await cleanup_expired_sessions(db, now=now)
        assert error.value is failure
    finally:
        event.remove(db.sync_session, "before_commit", fail_commit)
    assert not db.in_transaction()
    async with db.begin():
        for model, expected in [
            (Session, 1),
            (Simulation, 1),
            (BankResult, 2),
            (BankResultReason, 2),
        ]:
            assert await db.scalar(select(func.count()).select_from(model)) == expected
