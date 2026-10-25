import httpx
import pytest_asyncio
from fastapi import FastAPI, Query

from app.errors import (
    HistoryUnavailable,
    SimulationDeleteFailed,
    SimulationNotFound,
    SimulationSaveFailed,
    register_exception_handlers,
)
from app.schemas.request_schema import SimulationCreate


@pytest_asyncio.fixture
async def error_client():
    app = FastAPI()
    register_exception_handlers(app)
    exceptions = {
        "save": SimulationSaveFailed,
        "missing": SimulationNotFound,
        "history": HistoryUnavailable,
        "delete": SimulationDeleteFailed,
    }

    @app.get("/errors/{kind}")
    async def fail(kind: str):
        raise exceptions[kind]() from RuntimeError("private-database-details")

    @app.post("/validate")
    async def validate(payload: SimulationCreate):
        raise AssertionError("Invalid input must not reach the endpoint")

    @app.get("/query")
    async def query(page: int = Query(ge=1)):
        raise AssertionError("Invalid query must not reach the endpoint")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
