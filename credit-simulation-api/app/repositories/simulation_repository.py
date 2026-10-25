from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bank_result import BankResult
from app.models.session import Session
from app.models.simulation import Simulation


class SimulationRepository:
    """Owner-scoped persistence for simulations and their result graph."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def add(self, simulation: Simulation) -> None:
        """Stage the graph assembled by the service, without flush or commit."""
        self._db.add(simulation)

    async def find_for_session(
        self, simulation_id: UUID, session_id: UUID, *, now: datetime
    ) -> Simulation | None:
        statement = (
            select(Simulation)
            .join(Session, Simulation.session_id == Session.id)
            .where(
                Simulation.id == simulation_id,
                Simulation.session_id == session_id,
                Session.expires_at > now,
            )
            .options(
                selectinload(Simulation.bank_results).selectinload(BankResult.reasons)
            )
        )
        return await self._db.scalar(statement)

    async def list_for_session(
        self, session_id: UUID, *, now: datetime, page: int, page_size: int
    ) -> Sequence[Simulation]:
        if page < 1 or not 1 <= page_size <= 50:
            raise ValueError("Invalid history pagination.")
        statement = (
            select(Simulation)
            .join(Session, Simulation.session_id == Session.id)
            .where(Simulation.session_id == session_id, Session.expires_at > now)
            .options(
                selectinload(Simulation.bank_results).load_only(
                    BankResult.bank, BankResult.status, raiseload=True
                )
            )
            .order_by(Simulation.created_at.desc(), Simulation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return (await self._db.scalars(statement)).all()

    async def count_for_session(self, session_id: UUID, *, now: datetime) -> int:
        statement = (
            select(func.count())
            .select_from(Simulation)
            .join(Session, Simulation.session_id == Session.id)
            .where(Simulation.session_id == session_id, Session.expires_at > now)
        )
        return (await self._db.scalar(statement)) or 0

    async def delete_for_session(
        self, simulation_id: UUID, session_id: UUID, *, now: datetime
    ) -> bool:
        """Delete atomically within the owner's scope; PostgreSQL cascades children.

        True means a row was deleted in the current transaction, not committed.
        Missing, foreign and expired-session records all return False.
        """
        active_owner = select(Session.id).where(
            Session.id == session_id, Session.expires_at > now
        )
        statement = (
            delete(Simulation)
            .where(
                Simulation.id == simulation_id,
                Simulation.session_id == session_id,
                Simulation.session_id.in_(active_owner),
            )
            .returning(Simulation.id)
        )
        return await self._db.scalar(statement) is not None
