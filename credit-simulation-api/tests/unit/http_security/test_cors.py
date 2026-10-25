import pytest

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("method", ["GET", "POST", "DELETE"])
async def test_cors_preflight_allows_configured_origin_and_credentials(
    security_client, method
):
    response = await security_client.options(
        "/protected",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    assert "Origin" in response.headers["Vary"]


@pytest.mark.parametrize(
    "origin,method,header",
    [
        ("https://evil.example", "POST", "content-type"),
        ("http://localhost:5173", "PATCH", "content-type"),
        ("http://localhost:5173", "POST", "x-unapproved"),
    ],
)
async def test_cors_preflight_rejects_unapproved_origin_method_or_headers(
    security_client, origin, method, header
):
    response = await security_client.options(
        "/protected",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": header,
        },
    )
    assert response.status_code == 400


async def test_cors_does_not_grant_response_access_to_foreign_origin(security_client):
    response = await security_client.get(
        "/protected", headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers


async def test_allowed_origin_gets_cors_headers_on_validation_error(security_client):
    response = await security_client.get(
        "/validate", headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 422
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
