import asyncio

import httpx
import pytest


@pytest.mark.asyncio
async def test_deadline_covers_reading_the_entire_response(
    adapter_factory, simulation_request
):
    closed = asyncio.Event()

    class PendingBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{"private":'
            await asyncio.Event().wait()

        async def aclose(self):
            closed.set()

    def handler(request):
        return httpx.Response(200, stream=PendingBody())

    client, adapter = adapter_factory(handler, timeout=0.02)
    async with client:
        result = await asyncio.wait_for(
            adapter.evaluate(simulation_request, "normal"), timeout=2
        )
    assert result.status == "failed"
    assert result.error.code == "TIMEOUT"
    assert closed.is_set()
    assert "private" not in result.model_dump_json()
