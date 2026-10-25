from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session


class SessionRepository:
    """Session persistence; token generation and transaction ownership stay outside."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def add(self, session: Session) -> None:
        """Stage a new session without flushing or committing the transaction."""
        self._db.add(session)

    async def delete_expired(self, *, now: datetime) -> int:
        """Delete expired sessions and descendants, without committing.

        Count in PostgreSQL to avoid loading credentials or all deleted IDs.
        """
        deleted = (
            delete(Session)
            .where(Session.expires_at <= now)
            .returning(Session.id)
            .cte("expired_sessions")
        )
        return (await self._db.scalar(select(func.count()).select_from(deleted))) or 0

    async def find_active_by_token_hash(
        self, token_hash: bytes, *, now: datetime
    ) -> Session | None:
        statement = select(Session).where(
            Session.token_hash == token_hash, Session.expires_at > now
        )
        return await self._db.scalar(statement)

    async def find_active_by_id(
        self, session_id: UUID, *, now: datetime, for_update: bool = False
    ) -> Session | None:
        """Optionally lock the session until the caller's transaction finishes.

        A lock coordinates writes with session deletion by cleanup. The service
        supplies the current instant and must keep the write transaction short.
        """
        statement = select(Session).where(Session.id == session_id)
        if not for_update:
            statement = statement.where(Session.expires_at > now)
        statement = statement.execution_options(populate_existing=True)
        if for_update:
            statement = statement.with_for_update()
        return await self._db.scalar(statement)
