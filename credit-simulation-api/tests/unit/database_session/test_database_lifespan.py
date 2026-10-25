import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app import main


@pytest.mark.asyncio
async def test_resources_are_created_only_at_startup_and_disposed(database_app):
    app = database_app.app
    assert not database_app.engines
    assert not hasattr(app.state, "session_factory")
    async with app.router.lifespan_context(app):
        engine = app.state.database_engine
        assert isinstance(engine, AsyncEngine)
        assert database_app.engines == [engine]
        assert isinstance(app.state.session_factory, async_sessionmaker)
        assert app.state.session_factory.kw["bind"] is engine
        assert app.state.session_factory.kw["expire_on_commit"] is False
        assert engine not in database_app.disposed
    assert database_app.disposed == [engine]
    assert app.state.http_client.is_closed


@pytest.mark.asyncio
async def test_engine_is_disposed_after_lifespan_failure(database_app):
    app = database_app.app
    failure = RuntimeError("application failure")
    with pytest.raises(RuntimeError) as error:
        async with app.router.lifespan_context(app):
            raise failure
    assert error.value is failure
    assert database_app.disposed == [app.state.database_engine]
    assert app.state.http_client.is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["factory", "http_client"])
async def test_partial_startup_failure_disposes_engine(
    monkeypatch, database_app, stage
):
    failure = RuntimeError("startup failure")

    def fail(*args, **kwargs):
        raise failure

    if stage == "factory":
        monkeypatch.setattr(main, "create_session_factory", fail)
    else:
        monkeypatch.setattr(main.httpx, "AsyncClient", fail)
    app = database_app.app
    with pytest.raises(RuntimeError) as error:
        async with app.router.lifespan_context(app):
            pytest.fail("Failed startup must not yield")
    assert error.value is failure
    assert database_app.disposed == database_app.engines


@pytest.mark.asyncio
async def test_apps_have_independent_database_resources(database_app):
    first = database_app.app
    second = main.create_app(database_app.settings)
    async with first.router.lifespan_context(first):
        async with second.router.lifespan_context(second):
            assert first.state.database_engine is not second.state.database_engine
            assert first.state.session_factory is not second.state.session_factory
        assert database_app.disposed == [second.state.database_engine]
        assert first.state.database_engine not in database_app.disposed
    assert database_app.disposed == [
        second.state.database_engine,
        first.state.database_engine,
    ]
