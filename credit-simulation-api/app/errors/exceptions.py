from app.schemas.error_schema import ApplicationErrorCode


class ApplicationException(Exception):
    status_code: int
    code: ApplicationErrorCode
    message: str

    def __init__(self) -> None:
        super().__init__(self.message)


class SimulationSaveFailed(ApplicationException):
    status_code = 503
    code: ApplicationErrorCode = "SIMULATION_SAVE_FAILED"
    message = "Não foi possível salvar a simulação. Tente novamente mais tarde."


class SimulationNotFound(ApplicationException):
    status_code = 404
    code: ApplicationErrorCode = "SIMULATION_NOT_FOUND"
    message = "Simulação não encontrada."


class HistoryUnavailable(ApplicationException):
    status_code = 503
    code: ApplicationErrorCode = "HISTORY_UNAVAILABLE"
    message = "Não foi possível consultar o histórico. Tente novamente mais tarde."


class SimulationDeleteFailed(ApplicationException):
    status_code = 503
    code: ApplicationErrorCode = "SIMULATION_DELETE_FAILED"
    message = "Não foi possível excluir a simulação. Tente novamente mais tarde."
