import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import SimulationSaveFailed
from app.integrations.bank_adapter import BankAdapter
from app.models.simulation import Simulation
from app.repositories.simulation_repository import SimulationRepository
from app.schemas.request_schema import (
    SimulationCreate,
    SimulationPagination,
    SimulationScenarios,
)
from app.schemas.response_schema import (
    SimulationCreatedResponse,
    SimulationDetailResponse,
    SimulationHistoryResponse,
)
from app.services.session_service import SessionService
from app.services.simulation_history_service import SimulationHistoryService
from app.services.simulation_mapping import store_bank_result


@dataclass(frozen=True)
class CreatedSimulation:
    response: SimulationCreatedResponse
    session_expires_at: datetime
    new_token: str | None = field(default=None, repr=False)


class SimulationService:
    """Coordinate evaluations and save only complete, committed simulations.

    Repositories and SessionService must use the supplied AsyncSession. No
    transaction may already be active when a public operation is invoked.
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: SimulationRepository,
        sessions: SessionService,
        bank_a: BankAdapter,
        bank_b: BankAdapter,
        history: SimulationHistoryService,
    ) -> None:
        self._db = db
        self._repository = repository
        self._sessions = sessions
        self._bank_a = bank_a
        self._bank_b = bank_b
        self._history = history

    async def list_history(
        self, token: str | None, pagination: SimulationPagination
    ) -> SimulationHistoryResponse:
        return await self._history.list_history(token, pagination)

    async def get_detail(
        self, simulation_id: UUID, token: str | None
    ) -> SimulationDetailResponse:
        return await self._history.get_detail(simulation_id, token)

    async def delete(self, simulation_id: UUID, token: str | None) -> None:
        await self._history.delete(simulation_id, token)

    async def create(
        self,
        request: SimulationCreate,
        scenarios: SimulationScenarios,
        token: str | None,
    ) -> CreatedSimulation:
        session_id: UUID | None = None
        try:
            # End the lookup transaction before waiting for external services.
            async with self._db.begin():
                session = await self._sessions.find_active(token, now=datetime.now(UTC))
                if session is not None:
                    session_id = session.id
        except (SQLAlchemyError, ConnectionRefusedError) as exc:
            raise SimulationSaveFailed() from exc

        # TaskGroup cancels the other request if an unexpected failure propagates.
        async with asyncio.TaskGroup() as tasks:
            bank_a = tasks.create_task(
                self._bank_a.evaluate(request, scenarios.bank_a_scenario)
            )
            bank_b = tasks.create_task(
                self._bank_b.evaluate(request, scenarios.bank_b_scenario)
            )
        now = datetime.now(UTC)
        results = [bank_a.result(), bank_b.result()]
        validated = SimulationCreatedResponse(
            id=uuid4(), created_at=now, results=results
        )
        try:
            async with self._db.begin():
                prepared = await self._sessions.prepare_for_simulation(
                    session_id, now=now
                )
                response = validated.model_copy(
                    update={"created_at": prepared.recorded_at}
                )
                simulation = Simulation(
                    id=response.id,
                    session=prepared.session,
                    created_at=prepared.recorded_at,
                    monthly_income_cents=request.monthly_income_cents,
                    requested_amount_cents=request.requested_amount_cents,
                    term_months=request.term_months,
                    bank_results=[
                        store_bank_result(result) for result in response.results
                    ],
                )
                self._repository.add(simulation)
                await self._db.flush()
                created = CreatedSimulation(
                    response=response,
                    session_expires_at=prepared.session.expires_at,
                    new_token=prepared.new_token,
                )
            # The transaction context has confirmed commit before exposing a token.
            return created
        except (SQLAlchemyError, ConnectionRefusedError) as exc:
            # A failed commit may be uncertain; do not claim the record cannot exist.
            raise SimulationSaveFailed() from exc
