from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models import BankResult, BankResultReason, Session, Simulation
from app.models.enums import Bank, BankErrorCode, BankResultStatus, RejectionCode

MAX_SAFE_INTEGER = 9007199254740991


def make_session(**overrides):
    now = datetime.now(UTC)
    values = {
        "token_hash": uuid4().bytes + uuid4().bytes,
        "created_at": now,
        "expires_at": now + timedelta(days=7),
    }
    return Session(**(values | overrides))


def make_simulation(session=None, **overrides):
    values = {
        "session": session if session is not None else make_session(),
        "created_at": datetime.now(UTC),
        "monthly_income_cents": 300000,
        "requested_amount_cents": 100000,
        "term_months": 12,
    }
    return Simulation(**(values | overrides))


def make_bank_result(simulation=None, status=BankResultStatus.APPROVED, **overrides):
    values = {
        "simulation": simulation if simulation is not None else make_simulation(),
        "bank": Bank.BANK_A,
        "status": status,
    }
    if status == BankResultStatus.APPROVED:
        values.update(
            amount_cents=100000,
            term_months=12,
            monthly_interest_rate_bps=180,
            installment_cents=9340,
        )
    elif status == BankResultStatus.FAILED:
        values.update(
            error_code=BankErrorCode.TIMEOUT, error_message="O banco não respondeu."
        )
    return BankResult(**(values | overrides))


def make_reason(bank_result=None, **overrides):
    values = {
        "bank_result": bank_result
        if bank_result is not None
        else make_bank_result(status=BankResultStatus.REJECTED),
        "code": RejectionCode.TERM_NOT_SUPPORTED,
        "message": "Prazo não oferecido.",
        "position": 0,
    }
    return BankResultReason(**(values | overrides))


@dataclass
class SimulationGraph:
    session: Session
    simulation: Simulation
    approved_result: BankResult
    rejected_result: BankResult


def make_graph():
    session = make_session()
    simulation = make_simulation(session, created_at=session.created_at)
    # Deliberately insert B before A and positions 1 before 0.
    rejected = make_bank_result(
        simulation, status=BankResultStatus.REJECTED, bank=Bank.BANK_B
    )
    rejected.reasons = [
        make_reason(rejected, position=1),
        make_reason(
            rejected,
            code=RejectionCode.INCOME_BELOW_MINIMUM,
            message="Renda abaixo do mínimo.",
            position=0,
        ),
    ]
    approved = make_bank_result(simulation)
    return SimulationGraph(session, simulation, approved, rejected)
