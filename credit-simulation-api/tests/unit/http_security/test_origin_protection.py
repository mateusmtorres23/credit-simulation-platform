import pytest

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("method", ["POST", "DELETE"])
@pytest.mark.parametrize(
    "origin",
    [
        None,
        "null",
        "https://evil.example",
        "http://localhost:5174",
        "http://localhost:5173.evil.example",
        "http://localhost:5173/",
    ],
)
async def test_write_requests_require_exact_allowed_origin(
    security_client, method, origin
):
    headers = {} if origin is None else {"Origin": origin}
    response = await security_client.request(method, "/protected", headers=headers)
    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "REQUEST_FORBIDDEN",
            "message": "A origem da solicitação não é permitida.",
        }
    }
    assert "Set-Cookie" not in response.headers


@pytest.mark.parametrize("method", ["POST", "DELETE"])
async def test_trusted_origin_allows_write(security_client, method):
    response = await security_client.request(
        method, "/protected", headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


async def test_duplicate_origin_headers_are_rejected(security_client):
    response = await security_client.post(
        "/protected",
        headers=[
            ("Origin", "http://localhost:5173"),
            ("Origin", "http://localhost:5173"),
        ],
    )
    assert response.status_code == 403


async def test_reads_do_not_require_origin(security_client):
    response = await security_client.get("/protected")
    assert response.status_code == 200


async def test_registered_validation_handler_is_used_in_real_app(security_client):
    response = await security_client.get("/validate?page=private-input")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "private-input" not in response.text
