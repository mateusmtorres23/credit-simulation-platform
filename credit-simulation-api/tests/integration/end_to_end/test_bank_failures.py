import pytest

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "query,statuses",
    [
        ("bank_b_scenario=unavailable", ["approved", "failed"]),
        (
            "bank_a_scenario=unavailable&bank_b_scenario=unavailable",
            ["failed", "failed"],
        ),
    ],
)
async def test_real_503_is_saved_as_failure_not_credit_rejection(
    real_api, e2e_payload, query, statuses
):
    response = await real_api.client.post(f"/api/simulations?{query}", json=e2e_payload)
    assert response.status_code == 201
    body = response.json()
    assert [result["status"] for result in body["results"]] == statuses
    for result in body["results"]:
        if result["status"] == "failed":
            assert result["error"] == {
                "code": "BANK_UNAVAILABLE",
                "message": "O banco está temporariamente indisponível.",
            }
    detail = await real_api.client.get(f"/api/simulations/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["results"] == body["results"]


async def test_real_slow_responses_preserve_a_and_timeout_b_after_five_seconds(
    real_api, e2e_payload
):
    response = await real_api.client.post(
        "/api/simulations?bank_a_scenario=slow&bank_b_scenario=slow",
        json=e2e_payload,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["results"][0]["bank"] == "bank_a"
    assert body["results"][0]["status"] == "approved"
    assert body["results"][1] == {
        "bank": "bank_b",
        "status": "failed",
        "error": {
            "code": "TIMEOUT",
            "message": "O banco não respondeu dentro do tempo limite.",
        },
    }
    # Re-reading a stored timeout must not perform a new bank evaluation.
    detail = await real_api.client.get(f"/api/simulations/{body['id']}")
    assert detail.json()["results"] == body["results"]
    assert (await real_api.client.get("/api/simulations")).json()["total"] == 1
