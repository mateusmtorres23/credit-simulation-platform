from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import create_autospec
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends

from app.config import Settings
from app.dependencies import get_simulation_service, require_trusted_origin
from app.main import create_app
from app.schemas.response_schema import (
    SimulationCreatedResponse,
    SimulationDetailResponse,
    SimulationHistoryResponse,
)
from app.services.simulation_service import CreatedSimulation, SimulationService


@pytest.fixture
def router_payload():
    return {
        "name": "Cliente Fictício",
        "email": "cliente@example.com",
        "cpf": "00000000000",
        "employer_cnpj": "00000000000000",
        "monthly_income_cents": 300000,
        "requested_amount_cents": 100000,
        "term_months": 12,
    }


@pytest_asyncio.fixture
async def router_context(settings_data):
    settings = Settings(
        _env_file=None, **settings_data, allowed_origins=["http://frontend.test"]
    )
    app = create_app(settings)
    service = create_autospec(SimulationService, instance=True)
    now = datetime.now(UTC).replace(microsecond=0)
    result = SimulationCreatedResponse(
        id=uuid4(),
        created_at=now,
        results=[
            {
                "bank": bank,
                "status": "failed",
                "error": {"code": "TIMEOUT", "message": "Sem resposta."},
            }
            for bank in ("bank_a", "bank_b")
        ],
    )
    service.create.return_value = CreatedSimulation(
        result, now + timedelta(days=7), "a" * 43
    )
    service.list_history.return_value = SimulationHistoryResponse(
        items=[], total=0, page=1, page_size=10
    )
    service.get_detail.return_value = SimulationDetailResponse(
        **result.model_dump(),
        request={
            "monthly_income_cents": 300000,
            "requested_amount_cents": 100000,
            "term_months": 12,
        },
    )

    def override(trusted: object = Depends(require_trusted_origin)):
        return service

    app.dependency_overrides[get_simulation_service] = override
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Origin": "http://frontend.test"},
        ) as client,
    ):
        yield SimpleNamespace(
            app=app, settings=settings, service=service, client=client, result=result
        )
