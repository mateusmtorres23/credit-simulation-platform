import hashlib

import pytest
from sqlalchemy import select

from app.models import Session, Simulation

pytestmark = pytest.mark.asyncio


async def test_real_banks_approve_and_saved_result_survives_history_and_deletion(
    real_api, e2e_payload
):
    client = real_api.client
    response = await client.post("/api/simulations", json=e2e_payload)
    assert response.status_code == 201
    body = response.json()
    assert [(item["bank"], item["status"]) for item in body["results"]] == [
        ("bank_a", "approved"),
        ("bank_b", "approved"),
    ]
    assert [item["offer"]["installment_cents"] for item in body["results"]] == [
        9340,
        9514,
    ]
    assert [item["offer"]["monthly_interest_rate_bps"] for item in body["results"]] == [
        180,
        210,
    ]
    token = client.cookies.get("credit_session")
    assert token
    async with real_api.engine.connect() as reader:
        owner = await reader.scalar(
            select(Session.id).where(
                Session.token_hash == hashlib.sha256(token.encode()).digest()
            )
        )
        assert owner is not None
        assert (
            await reader.scalar(
                select(Simulation.id).where(Simulation.session_id == owner)
            )
            is not None
        )
    history = await client.get("/api/simulations")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    detail = await client.get(f"/api/simulations/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["results"] == body["results"]
    assert set(detail.json()["request"]) == {
        "monthly_income_cents",
        "requested_amount_cents",
        "term_months",
    }
    assert "cliente@example.com" not in detail.text
    removed = await client.delete(f"/api/simulations/{body['id']}")
    assert removed.status_code == 204
    assert removed.content == b""
    assert "set-cookie" not in removed.headers
    assert (await client.get(f"/api/simulations/{body['id']}")).status_code == 404
    assert (await client.get("/api/simulations")).json()["total"] == 0


@pytest.mark.parametrize(
    "term,statuses", [(6, ["approved", "rejected"]), (60, ["rejected", "approved"])]
)
async def test_real_bank_policies_are_preserved_and_reasons_translated(
    real_api, e2e_payload, term, statuses
):
    response = await real_api.client.post(
        "/api/simulations", json=e2e_payload | {"term_months": term}
    )
    assert response.status_code == 201
    results = response.json()["results"]
    assert [item["status"] for item in results] == statuses
    rejected = next(item for item in results if item["status"] == "rejected")
    assert rejected["reasons"] == [
        {
            "code": "TERM_NOT_SUPPORTED",
            "message": "O banco não oferece o prazo solicitado.",
        }
    ]


async def test_low_income_is_rejected_by_both_real_contracts(real_api, e2e_payload):
    response = await real_api.client.post(
        "/api/simulations", json=e2e_payload | {"monthly_income_cents": 100000}
    )
    assert response.status_code == 201
    for result in response.json()["results"]:
        assert result["status"] == "rejected"
        assert result["reasons"][0]["code"] == "INCOME_BELOW_MINIMUM"
