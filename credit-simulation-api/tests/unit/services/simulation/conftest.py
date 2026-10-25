from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, create_autospec
from uuid import uuid4

import pytest_asyncio
from factories import make_session
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.bank_adapter import BankAdapter
from app.repositories.simulation_repository import SimulationRepository
from app.schemas.bank_result_schema import ApprovedBankResult, BankOffer
from app.schemas.request_schema import SimulationCreate, SimulationScenarios
from app.services.session_service import PreparedSession, SessionService
from app.services.simulation_history_service import SimulationHistoryService
from app.services.simulation_service import SimulationService


@pytest_asyncio.fixture
async def simulation_context():
    async with AsyncSession() as db:
        db.flush = AsyncMock()
        repo = create_autospec(SimulationRepository, instance=True)
        sessions = create_autospec(SessionService, instance=True)
        sessions.find_active.return_value = None
        sessions.prepare_for_simulation.return_value = PreparedSession(
            make_session(id=uuid4()), "private-token"
        )
        banks = [create_autospec(BankAdapter, instance=True) for _ in range(2)]
        for bank, name in zip(banks, ["bank_a", "bank_b"], strict=True):
            bank.evaluate.return_value = ApprovedBankResult(
                bank=name,
                status="approved",
                offer=BankOffer(
                    amount_cents=100000,
                    term_months=12,
                    monthly_interest_rate_bps=180,
                    installment_cents=9340,
                ),
            )
        history = SimulationHistoryService(db, repo, sessions)
        service = SimulationService(db, repo, sessions, *banks, history)
        yield SimpleNamespace(
            db=db,
            repo=repo,
            sessions=sessions,
            banks=banks,
            service=service,
            request=SimulationCreate(
                name="Cliente Fictício",
                email="cliente@example.com",
                cpf="00000000000",
                employer_cnpj="00000000000000",
                monthly_income_cents=300000,
                requested_amount_cents=100000,
                term_months=12,
            ),
            scenarios=SimulationScenarios(),
            now=datetime.now(UTC),
        )
