import pytest
from sqlalchemy import event, func, select

from app.models import Session

pytestmark = pytest.mark.asyncio


async def test_history_returns_empty_for_pages_after_last_without_invalid_offset(
    http_stack, http_payload
):
    ctx = http_stack
    for _ in range(2):
        response = await ctx.client.post("/api/simulations", json=http_payload)
        assert response.status_code == 201

    last_page = await ctx.client.get("/api/simulations?page=3&page_size=1")
    assert last_page.status_code == 200
    assert last_page.json() == {
        "items": [],
        "total": 2,
        "page": 3,
        "page_size": 1,
    }

    normal = await ctx.client.get("/api/simulations?page=1&page_size=1")
    assert normal.status_code == 200
    assert normal.json()["total"] == 2
    assert len(normal.json()["items"]) == 1
    assert normal.json()["page"] == 1
    assert normal.json()["page_size"] == 1

    huge_page = 99999999999999999999999999999999
    statements = []
    target = ctx.db.sync_session.get_bind()

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.upper())

    event.listen(target, "before_cursor_execute", capture)
    try:
        extreme = await ctx.client.get(
            f"/api/simulations?page={huge_page}&page_size=50"
        )
    finally:
        event.remove(target, "before_cursor_execute", capture)

    assert extreme.status_code == 200
    assert extreme.json() == {
        "items": [],
        "total": 2,
        "page": huge_page,
        "page_size": 50,
    }
    assert not any(" OFFSET " in statement for statement in statements)
    assert len(ctx.calls) == 4


async def test_extreme_page_on_empty_history_does_not_create_session_or_call_banks(
    http_stack,
):
    response = await http_stack.client.get(
        "/api/simulations?page=99999999999999999999999999999999&page_size=1"
    )
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 99999999999999999999999999999999,
        "page_size": 1,
    }
    assert "set-cookie" not in response.headers
    assert not http_stack.calls
    async with http_stack.db.begin():
        assert (
            await http_stack.db.scalar(select(func.count()).select_from(Session)) == 0
        )
