from datetime import UTC, datetime, timedelta

import pytest
from factories import make_graph
from sqlalchemy import func, select

from app.cleanup import cleanup_expired_sessions
from app.models import BankResult, BankResultReason, Session, Simulation

pytestmark = pytest.mark.asyncio


async def test_cleanup_deletes_expired_graphs_preserves_valid_and_is_idempotent(db):
    now = datetime.now(UTC)
    graphs = [make_graph() for _ in range(3)]
    for graph, expiry in zip(
        graphs,
        [now - timedelta(microseconds=1), now, now + timedelta(microseconds=1)],
        strict=True,
    ):
        graph.session.created_at = now - timedelta(days=7)
        graph.session.expires_at = expiry
        db.add(graph.session)
    await db.commit()
    expired_ids = [graph.session.id for graph in graphs[:2]]
    valid_id = graphs[2].session.id
    assert await cleanup_expired_sessions(db, now=now) == 2
    db.expunge_all()
    async with db.begin():
        for session_id in expired_ids:
            assert await db.get(Session, session_id) is None
        assert await db.get(Session, valid_id) is not None
        for model, expected in [
            (Session, 1),
            (Simulation, 1),
            (BankResult, 2),
            (BankResultReason, 2),
        ]:
            assert await db.scalar(select(func.count()).select_from(model)) == expected
    assert await cleanup_expired_sessions(db, now=now) == 0


async def test_cleanup_empty_database_returns_zero(db):
    assert await cleanup_expired_sessions(db) == 0
