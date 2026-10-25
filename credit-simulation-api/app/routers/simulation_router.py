from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.dependencies import (
    SESSION_COOKIE_NAME,
    SessionTokenDependency,
    SettingsDependency,
    SimulationServiceDependency,
)
from app.schemas.error_schema import ErrorResponse
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

router = APIRouter(
    prefix="/api/simulations",
    tags=["simulations"],
    responses={
        422: {"model": ErrorResponse, "description": "Solicitação inválida."},
        503: {"model": ErrorResponse, "description": "Operação indisponível."},
    },
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SimulationCreatedResponse,
    responses={403: {"model": ErrorResponse, "description": "Origem não permitida."}},
)
async def create_simulation(
    payload: SimulationCreate,
    scenarios: Annotated[SimulationScenarios, Query()],
    service: SimulationServiceDependency,
    token: SessionTokenDependency,
    settings: SettingsDependency,
    response: Response,
) -> SimulationCreatedResponse:
    created = await service.create(payload, scenarios, token)
    if created.new_token is not None:
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=created.new_token,
            expires=created.session_expires_at,
            path="/api",
            secure=settings.session_cookie_secure,
            httponly=True,
            samesite="lax",
        )
    return created.response


@router.get("", response_model=SimulationHistoryResponse)
async def list_simulations(
    pagination: Annotated[SimulationPagination, Query()],
    service: SimulationServiceDependency,
    token: SessionTokenDependency,
) -> SimulationHistoryResponse:
    return await service.list_history(token, pagination)


@router.get(
    "/{simulation_id}",
    response_model=SimulationDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Simulação não encontrada."}
    },
)
async def get_simulation(
    simulation_id: UUID,
    service: SimulationServiceDependency,
    token: SessionTokenDependency,
) -> SimulationDetailResponse:
    return await service.get_detail(simulation_id, token)


@router.delete(
    "/{simulation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        403: {"model": ErrorResponse, "description": "Origem não permitida."},
        404: {"model": ErrorResponse, "description": "Simulação não encontrada."},
    },
)
async def delete_simulation(
    simulation_id: UUID,
    service: SimulationServiceDependency,
    token: SessionTokenDependency,
) -> Response:
    await service.delete(simulation_id, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
