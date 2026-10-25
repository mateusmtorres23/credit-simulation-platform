from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import HistoryUnavailable, SimulationDeleteFailed, SimulationNotFound
from app.repositories.simulation_repository import SimulationRepository
from app.schemas.request_schema import SimulationPagination
from app.schemas.response_schema import (
    SimulationDetailResponse,
    SimulationHistoryResponse,
)
from app.services.session_service import SessionService
from app.services.simulation_mapping import simulation_detail, simulation_summary


class SimulationHistoryService:
    """Read and delete saved evaluations without consulting banks.

    All dependencies must share the same request-scoped AsyncSession, with no
    active transaction on entry. This service owns its transaction boundaries.
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: SimulationRepository,
        sessions: SessionService,
    ) -> None:
        self._db = db
        self._repository = repository
        self._sessions = sessions

    async def list_history(
        self, token: str | None, pagination: SimulationPagination
    ) -> SimulationHistoryResponse:
        now = datetime.now(UTC)
        try:
            async with self._db.begin():
                session = await self._sessions.find_active(token, now=now)
                items = []
                total = 0
                if session is not None:
                    total = await self._repository.count_for_session(
                        session.id, now=now
                    )
                    pages = (total + pagination.page_size - 1) // pagination.page_size
                    if pagination.page <= pages:
                        records = await self._repository.list_for_session(
                            session.id,
                            now=now,
                            page=pagination.page,
                            page_size=pagination.page_size,
                        )
                        items = [simulation_summary(record) for record in records]
                    if session.expires_at <= self._sessions.current_time():
                        items = []
                        total = 0
                response = SimulationHistoryResponse(
                    items=items,
                    total=total,
                    page=pagination.page,
                    page_size=pagination.page_size,
                )
            return response
        except (SQLAlchemyError, ConnectionRefusedError) as exc:
            raise HistoryUnavailable() from exc

    async def get_detail(
        self, simulation_id: UUID, token: str | None
    ) -> SimulationDetailResponse:
        now = datetime.now(UTC)
        try:
            async with self._db.begin():
                session = await self._sessions.find_active(token, now=now)
                if session is None:
                    raise SimulationNotFound()
                record = await self._repository.find_for_session(
                    simulation_id, session.id, now=now
                )
                if (
                    record is None
                    or session.expires_at <= self._sessions.current_time()
                ):
                    raise SimulationNotFound()
                response = simulation_detail(record)
            return response
        except (SQLAlchemyError, ConnectionRefusedError) as exc:
            raise HistoryUnavailable() from exc

    async def delete(self, simulation_id: UUID, token: str | None) -> None:
        now = datetime.now(UTC)
        try:
            async with self._db.begin():
                session = await self._sessions.find_active(token, now=now)
                if session is None:
                    raise SimulationNotFound()
                session = await self._sessions.revalidate_for_write(session.id, now=now)
                if session is None or not await self._repository.delete_for_session(
                    simulation_id, session.id, now=self._sessions.current_time()
                ):
                    raise SimulationNotFound()
        except (SQLAlchemyError, ConnectionRefusedError) as exc:
            raise SimulationDeleteFailed() from exc
