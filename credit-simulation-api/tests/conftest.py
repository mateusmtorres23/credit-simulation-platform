import os
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run PostgreSQL integration tests using Docker/Testcontainers",
    )


def pytest_collection_modifyitems(config, items):
    integration_directory = Path(__file__).parent / "integration"
    for item in items:
        if item.path.is_relative_to(integration_directory):
            item.add_marker(pytest.mark.integration)
            if not config.getoption("--run-integration"):
                item.add_marker(
                    pytest.mark.skip(
                        reason="Use --run-integration to enable Docker tests"
                    )
                )


@pytest.fixture
def settings_data(monkeypatch):
    for key in list(os.environ):
        if key.upper().startswith("POSTGRES_"):
            monkeypatch.delenv(key)
    return {
        "postgres_user": "test_user",
        "postgres_password": "test_password",
        "postgres_db": "test_db",
        "postgres_host": "localhost",
        "postgres_port": 5432,
    }
