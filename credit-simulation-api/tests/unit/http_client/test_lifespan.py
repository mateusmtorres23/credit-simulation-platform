import httpx
import pytest

from app import main


@pytest.mark.asyncio
async def test_client_is_shared_configured_and_closed(http_settings):
    app = main.create_app(http_settings)
    assert not hasattr(app.state, "http_client")
    async with app.router.lifespan_context(app):
        client = app.state.http_client
        assert isinstance(client, httpx.AsyncClient)
        assert not client.is_closed
        assert app.state.settings is http_settings
        assert client.timeout == httpx.Timeout(http_settings.bank_timeout_seconds)
        assert app.state.http_client is client
    assert client.is_closed


@pytest.mark.asyncio
async def test_client_closes_when_lifespan_exits_with_exception(http_settings):
    app = main.create_app(http_settings)
    failure = RuntimeError("application failure")
    with pytest.raises(RuntimeError) as error:
        async with app.router.lifespan_context(app):
            client = app.state.http_client
            raise failure
    assert error.value is failure
    assert client.is_closed


@pytest.mark.asyncio
async def test_each_app_owns_its_client(http_settings):
    first = main.create_app(http_settings)
    second = main.create_app(http_settings)
    async with first.router.lifespan_context(first):
        async with second.router.lifespan_context(second):
            assert first.state.http_client is not second.state.http_client
        assert second.state.http_client.is_closed
        assert not first.state.http_client.is_closed
    assert first.state.http_client.is_closed


@pytest.mark.asyncio
async def test_settings_are_loaded_at_startup(monkeypatch, settings_data):
    for key, value in settings_data.items():
        monkeypatch.setenv(key.upper(), str(value))
    monkeypatch.setenv("BANK_TIMEOUT_SECONDS", "1.75")
    app = main.create_app()
    assert not hasattr(app.state, "settings")
    async with app.router.lifespan_context(app):
        assert app.state.settings.bank_timeout_seconds == 1.75
        assert app.state.http_client.timeout == httpx.Timeout(1.75)


@pytest.mark.asyncio
async def test_explicit_settings_skip_environment_loading(monkeypatch, http_settings):
    def fail_settings():
        raise AssertionError("Explicit settings must be reused")

    monkeypatch.setattr(main, "Settings", fail_settings)
    app = main.create_app(http_settings)
    async with app.router.lifespan_context(app):
        assert app.state.settings is http_settings


@pytest.mark.asyncio
async def test_invalid_startup_settings_do_not_publish_client(monkeypatch):
    failure = ValueError("invalid configuration")

    def fail_settings():
        raise failure

    monkeypatch.setattr(main, "Settings", fail_settings)
    app = main.create_app()
    with pytest.raises(ValueError) as error:
        async with app.router.lifespan_context(app):
            pytest.fail("Startup must fail before yielding")
    assert error.value is failure
    assert not hasattr(app.state, "http_client")
