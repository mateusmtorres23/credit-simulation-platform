import pytest
from sqlalchemy import inspect

from app.schemas.bank_result_schema import FailedBankResult, RejectedBankResult
from app.schemas.request_schema import SimulationPagination

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "outcome", ["approved", "rejected", "partial_failure", "total_failure"]
)
async def test_create_detail_and_history_preserve_results_and_minimize_data(
    persisted_service, outcome
):
    ctx = persisted_service
    for index, bank in enumerate(ctx.banks):
        name = f"bank_{'ab'[index]}"
        if outcome == "rejected":
            bank.evaluate.return_value = RejectedBankResult(
                bank=name,
                status="rejected",
                reasons=[
                    {"code": "TERM_NOT_SUPPORTED", "message": "Prazo não oferecido."},
                    {"code": "INCOME_BELOW_MINIMUM", "message": "Renda insuficiente."},
                ],
            )
        elif outcome == "total_failure" or (
            outcome == "partial_failure" and index == 1
        ):
            bank.evaluate.return_value = FailedBankResult(
                bank=name,
                status="failed",
                error={"code": "TIMEOUT", "message": "Tempo limite excedido."},
            )
    created = await ctx.service.create(ctx.request, ctx.scenarios, None)
    assert not ctx.db.in_transaction()
    assert created.new_token
    ctx.db.expunge_all()
    detail = await ctx.service.get_detail(created.response.id, created.new_token)
    assert detail.results == created.response.results
    assert detail.request.model_dump() == {
        "monthly_income_cents": 300000,
        "requested_amount_cents": 100000,
        "term_months": 12,
    }
    ctx.db.expunge_all()
    history = await ctx.service.list_history(created.new_token, SimulationPagination())
    assert history.total == 1
    assert history.items[0].id == created.response.id
    assert [result.status for result in history.items[0].results] == [
        result.status for result in created.response.results
    ]
    for bank in ctx.banks:
        assert bank.evaluate.await_count == 1
    assert "cliente@example.com" not in detail.model_dump_json()
    record = ctx.db.identity_map.values()
    assert all("cpf" not in inspect(item).mapper.attrs for item in record)


async def test_existing_session_is_not_renewed_and_history_is_paginated(
    persisted_service, service_clock
):
    ctx = persisted_service
    first = await ctx.service.create(ctx.request, ctx.scenarios, None)
    second = await ctx.service.create(ctx.request, ctx.scenarios, first.new_token)
    assert second.new_token is None
    assert second.session_expires_at == first.session_expires_at
    first_page = await ctx.service.list_history(
        first.new_token, SimulationPagination(page_size=1)
    )
    second_page = await ctx.service.list_history(
        first.new_token, SimulationPagination(page=2, page_size=1)
    )
    expected = sorted([first.response.id, second.response.id], reverse=True)
    assert first_page.total == second_page.total == 2
    assert [first_page.items[0].id, second_page.items[0].id] == expected
