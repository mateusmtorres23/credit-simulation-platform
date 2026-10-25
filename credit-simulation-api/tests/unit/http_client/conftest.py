import pytest

from app.config import Settings


@pytest.fixture(autouse=True)
def isolate_bank_environment(monkeypatch):
    for name in ("BANK_A_BASE_URL", "BANK_B_BASE_URL", "BANK_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def http_settings(settings_data):
    return Settings(_env_file=None, **settings_data)
