from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.integrations.bank_adapter import BankAdapter
from app.repositories.session_repository import SessionRepository
from app.repositories.simulation_repository import SimulationRepository
from app.schemas.bank_result_schema import ApprovedBankResult, BankOffer
from app.schemas.request_schema import SimulationCreate, SimulationScenarios
from app.services import simulation_history_service, simulation_service
from app.services.session_service import SessionService
from app.services.simulation_history_service import SimulationHistoryService
from app.services.simulation_service import SimulationService


@pytest.fixture
def service_clock(monkeypatch):
    clock = SimpleNamespace(now=datetime.now(UTC))

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.now if tz is None else clock.now.astimezone(tz)

    monkeypatch.setattr(simulation_service, "datetime", Clock)
    monkeypatch.setattr(simulation_history_service, "datetime", Clock)
    return clock


@pytest.fixture
def build_service(service_clock):
    def build(db):
        repo = SimulationRepository(db)
        sessions = SessionService(SessionRepository(db))
        banks = [AsyncMock(spec=BankAdapter), AsyncMock(spec=BankAdapter)]
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
        return SimpleNamespace(
            service=SimulationService(db, repo, sessions, *banks, history),
            sessions=sessions,
            banks=banks,
            db=db,
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
        )

    return build


@pytest.fixture
def persisted_service(db, build_service):
    return build_service(db)
