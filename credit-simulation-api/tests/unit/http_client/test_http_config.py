import pytest
from pydantic import ValidationError

from app.config import Settings


def test_bank_defaults(http_settings):
    assert str(http_settings.bank_a_base_url) == "http://localhost:3001/"
    assert str(http_settings.bank_b_base_url) == "http://localhost:3002/"
    assert http_settings.bank_timeout_seconds == 5.0


@pytest.mark.parametrize("field", ["bank_a_base_url", "bank_b_base_url"])
@pytest.mark.parametrize("url", ["http://bank-a:3001", "https://bank.example/api/"])
def test_http_and_https_bank_addresses_are_configurable(settings_data, field, url):
    settings = Settings(_env_file=None, **settings_data, **{field: url})
    assert str(getattr(settings, field)) == url.rstrip("/") + "/"


@pytest.mark.parametrize("field", ["bank_a_base_url", "bank_b_base_url"])
@pytest.mark.parametrize("value", ["", " \t", "bank-a:3001", "ftp://bank.example", 123])
def test_invalid_bank_addresses_are_rejected(settings_data, field, value):
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, **settings_data, **{field: value})
    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize(
    "value", [0, -1, float("nan"), float("inf"), -float("inf"), "bad"]
)
def test_timeout_must_be_positive_and_finite(settings_data, value):
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, **settings_data, bank_timeout_seconds=value)
    assert error.value.errors()[0]["loc"] == ("bank_timeout_seconds",)


@pytest.mark.parametrize("value", [0.1, 1, 12.5])
def test_positive_fractional_and_integer_timeouts_are_supported(settings_data, value):
    settings = Settings(_env_file=None, **settings_data, bank_timeout_seconds=value)
    assert settings.bank_timeout_seconds == value


def test_bank_dotenv_environment_and_explicit_value_precedence(
    tmp_path, monkeypatch, settings_data
):
    path = tmp_path / ".env"
    path.write_text(
        "BANK_A_BASE_URL=http://file-a:3001\n"
        "BANK_B_BASE_URL=http://file-b:3002\nBANK_TIMEOUT_SECONDS=2.5\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=path, **settings_data)
    assert str(settings.bank_a_base_url) == "http://file-a:3001/"
    assert str(settings.bank_b_base_url) == "http://file-b:3002/"
    assert settings.bank_timeout_seconds == 2.5
    monkeypatch.setenv("BANK_A_BASE_URL", "https://env-a.example")
    monkeypatch.setenv("BANK_B_BASE_URL", "https://env-b.example")
    monkeypatch.setenv("BANK_TIMEOUT_SECONDS", "3.5")
    settings = Settings(_env_file=path, **settings_data)
    assert str(settings.bank_a_base_url) == "https://env-a.example/"
    assert str(settings.bank_b_base_url) == "https://env-b.example/"
    assert settings.bank_timeout_seconds == 3.5
    explicit = Settings(_env_file=path, **settings_data, bank_timeout_seconds=4.5)
    assert explicit.bank_timeout_seconds == 4.5
