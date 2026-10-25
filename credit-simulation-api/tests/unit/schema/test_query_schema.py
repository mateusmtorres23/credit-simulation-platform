import pytest
from pydantic import ValidationError

from app.schemas.request_schema import (
    SimulationPagination,
    SimulationScenarios,
)


@pytest.mark.parametrize(
    "changes",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 51},
        {"page": "invalid"},
        {"page_size": 1.5},
    ],
)
def test_pagination_limits(changes):
    with pytest.raises(ValidationError):
        SimulationPagination(**changes)


def test_query_defaults_and_numeric_strings():
    assert SimulationPagination().model_dump() == {"page": 1, "page_size": 10}
    assert SimulationPagination(page="2", page_size="50").model_dump() == {
        "page": 2,
        "page_size": 50,
    }
    assert SimulationScenarios().model_dump() == {
        "bank_a_scenario": "normal",
        "bank_b_scenario": "normal",
    }
    assert (
        SimulationScenarios(
            bank_a_scenario="slow", bank_b_scenario="unavailable"
        ).bank_a_scenario
        == "slow"
    )


@pytest.mark.parametrize("field", ["bank_a_scenario", "bank_b_scenario"])
def test_scenarios_reject_unknown_modes(field):
    with pytest.raises(ValidationError):
        SimulationScenarios(**{field: "unstable"})
