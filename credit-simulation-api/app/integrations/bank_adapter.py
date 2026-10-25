from typing import Protocol

from app.schemas.bank_result_schema import BankResult
from app.schemas.request_schema import BankScenario, SimulationCreate


class BankAdapter(Protocol):
    """Target interface for bank evaluations, independent of external contracts."""

    async def evaluate(
        self, request: SimulationCreate, scenario: BankScenario
    ) -> BankResult:
        """Return a normalized decision or technical failure within the deadline.

        Implementations translate and validate the bank's HTTP contract, enforce
        the configured total timeout, and do not retry or persist request data.
        Cancellation and unexpected programming errors must propagate.
        """
        ...
