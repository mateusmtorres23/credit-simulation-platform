import asyncio

import httpx
import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code,message",
    [
        (503, "BANK_UNAVAILABLE", "O banco está temporariamente indisponível."),
        (
            400,
            "INVALID_BANK_RESPONSE",
            "Não foi possível interpretar a resposta do banco.",
        ),
        (
            500,
            "INVALID_BANK_RESPONSE",
            "Não foi possível interpretar a resposta do banco.",
        ),
        (
            302,
            "INVALID_BANK_RESPONSE",
            "Não foi possível interpretar a resposta do banco.",
        ),
    ],
)
async def test_http_failures_are_sanitized_without_retry_or_redirect(
    bank_case, adapter_factory, simulation_request, status, code, message
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            content=b"private-response",
            headers={"Location": "http://other.test/"},
        )

    client, adapter = adapter_factory(handler)
    async with client:
        result = await adapter.evaluate(simulation_request, "normal")
    assert len(calls) == 1
    assert result.model_dump(mode="json") == {
        "bank": f"bank_{bank_case}",
        "status": "failed",
        "error": {"code": code, "message": message},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception_class,code",
    [
        (httpx.ConnectTimeout, "TIMEOUT"),
        (httpx.ReadTimeout, "TIMEOUT"),
        (httpx.WriteTimeout, "TIMEOUT"),
        (httpx.PoolTimeout, "TIMEOUT"),
        (httpx.ConnectError, "BANK_UNAVAILABLE"),
        (httpx.ReadError, "BANK_UNAVAILABLE"),
        (httpx.ProxyError, "BANK_UNAVAILABLE"),
        (httpx.RemoteProtocolError, "INVALID_BANK_RESPONSE"),
        (httpx.DecodingError, "INVALID_BANK_RESPONSE"),
    ],
)
async def test_transport_errors_are_normalized_without_leaking_details(
    adapter_factory, simulation_request, exception_class, code
):
    calls = []

    def handler(request):
        calls.append(request)
        raise exception_class("private-transport-details", request=request)

    client, adapter = adapter_factory(handler)
    async with client:
        result = await adapter.evaluate(simulation_request, "normal")
    assert len(calls) == 1
    assert result.status == "failed"
    assert result.error.code == code
    assert "private-" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_total_deadline_cancels_a_pending_request(
    adapter_factory, simulation_request
):
    cancelled = asyncio.Event()

    async def handler(request):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    client, adapter = adapter_factory(handler, timeout=0.02)
    async with client:
        result = await asyncio.wait_for(adapter.evaluate(simulation_request, "slow"), 2)
        assert not client.is_closed
    assert cancelled.is_set()
    assert result.error.code == "TIMEOUT"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [asyncio.CancelledError, RuntimeError])
async def test_cancellation_and_programming_errors_propagate(
    adapter_factory, simulation_request, failure
):
    async def handler(request):
        raise failure("do not swallow")

    client, adapter = adapter_factory(handler)
    async with client:
        with pytest.raises(failure):
            await adapter.evaluate(simulation_request, "normal")
