import pytest

from app.errors import (
    ApplicationException,
    HistoryUnavailable,
    SimulationDeleteFailed,
    SimulationNotFound,
    SimulationSaveFailed,
)


@pytest.mark.parametrize(
    "exception_class,status,code,message",
    [
        (
            SimulationSaveFailed,
            503,
            "SIMULATION_SAVE_FAILED",
            "Não foi possível salvar a simulação. Tente novamente mais tarde.",
        ),
        (SimulationNotFound, 404, "SIMULATION_NOT_FOUND", "Simulação não encontrada."),
        (
            HistoryUnavailable,
            503,
            "HISTORY_UNAVAILABLE",
            "Não foi possível consultar o histórico. Tente novamente mais tarde.",
        ),
        (
            SimulationDeleteFailed,
            503,
            "SIMULATION_DELETE_FAILED",
            "Não foi possível excluir a simulação. Tente novamente mais tarde.",
        ),
    ],
)
def test_application_exceptions_expose_only_controlled_public_messages(
    exception_class, status, code, message
):
    try:
        raise exception_class() from RuntimeError("private-database-details")
    except ApplicationException as exc:
        assert exc.status_code == status
        assert exc.code == code
        assert exc.message == message
        assert str(exc) == message
        assert exc.args == (message,)
        assert "private-database-details" not in str(exc)
