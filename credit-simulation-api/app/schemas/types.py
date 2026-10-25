from datetime import UTC, datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

MAX_SAFE_INTEGER = 9007199254740991


PositiveMoney = Annotated[int, Field(strict=True, ge=1, le=MAX_SAFE_INTEGER)]


RequestedAmount = Annotated[int, Field(strict=True, ge=100, le=MAX_SAFE_INTEGER)]


TermMonths = Annotated[int, Field(strict=True, ge=1, le=120)]


MonthlyInterestRate = Annotated[int, Field(strict=True, ge=0, le=MAX_SAFE_INTEGER)]


def _require_nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("Message must not be blank.")
    return value


NonblankText = Annotated[
    str, StringConstraints(strict=True, min_length=1), AfterValidator(_require_nonblank)
]


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


SimulationTimestamp = Annotated[AwareDatetime, AfterValidator(_to_utc)]


class SimulationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
