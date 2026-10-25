import asyncio
import hashlib
from contextlib import asynccontextmanager

from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session
from app.repositories.session_repository import SessionRepository


def observe_lock_request(operation_db):
    requested = asyncio.Event()

    def before_execute(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ):
        if "FOR UPDATE" in statement.upper():
            requested.set()

    target = operation_db.sync_session.get_bind()
    event.listen(target, "before_cursor_execute", before_execute)
    return requested, target, before_execute


@asynccontextmanager
async def locked_session(engine, session_id, now):
    locker = AsyncSession(engine)
    try:
        await locker.begin()
        locked = await SessionRepository(locker).find_active_by_id(
            session_id, now=now, for_update=True
        )
        if locked is None:
            raise AssertionError("The test session could not be locked.")
        yield locker
    finally:
        if locker.in_transaction():
            await locker.rollback()
        await locker.close()


@asynccontextmanager
async def locked_simulations(engine):
    locker = AsyncSession(engine)
    try:
        await locker.begin()
        await locker.execute(text("LOCK TABLE simulations IN ACCESS EXCLUSIVE MODE"))
        yield locker
    finally:
        if locker.in_transaction():
            await locker.rollback()
        await locker.close()


async def backend_pid(session):
    return await session.scalar(text("SELECT pg_backend_pid()"))


async def wait_for_blocking(engine, locker_pid, query_fragment="FOR UPDATE"):
    async def observe():
        while True:
            async with engine.connect() as observer:
                row = (
                    await observer.execute(
                        text(
                            """
                            SELECT pid, pg_blocking_pids(pid)
                            FROM pg_stat_activity
                            WHERE wait_event_type = 'Lock'
                              AND query ILIKE :query_fragment
                            """
                        ).bindparams(query_fragment=f"%{query_fragment}%"),
                    )
                ).one_or_none()
                if row is not None and locker_pid in row[1]:
                    return row[0]
            await asyncio.sleep(0.02)

    return await asyncio.wait_for(observe(), timeout=5)


def http_payload():
    return {
        "name": "Cliente Fictício",
        "email": "cliente@example.com",
        "cpf": "00000000000",
        "employer_cnpj": "00000000000000",
        "monthly_income_cents": 300000,
        "requested_amount_cents": 100000,
        "term_months": 12,
    }


async def session_by_token(engine, token):
    async with engine.connect() as reader:
        return (
            await reader.execute(
                select(Session).where(
                    Session.token_hash == hashlib.sha256(token.encode()).digest()
                )
            )
        ).one()
