import pytest
from pydantic import ValidationError

from app.config import Settings


def test_security_defaults_are_local_and_deny_unconfigured_origins(settings_data):
    settings = Settings(_env_file=None, **settings_data)
    assert settings.session_cookie_secure is False
    assert settings.allowed_origins == []


def test_origins_are_normalized_and_deduplicated(settings_data):
    settings = Settings(
        _env_file=None,
        **settings_data,
        allowed_origins=[
            "HTTP://LOCALHOST:80/",
            "http://localhost",
            "https://example.com:443",
            "http://[::1]:5173",
            "https://example.com:8443",
        ],
    )
    assert settings.allowed_origins == [
        "http://localhost",
        "https://example.com",
        "http://[::1]:5173",
        "https://example.com:8443",
    ]


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://*.example.com",
        "null",
        "",
        "example.com",
        "ftp://example.com",
        "https://example.com/path",
        "https://example.com/path/..",
        "https://example.com?x=1",
        "https://example.com#part",
        "https://user:secret@example.com",
        " https://example.com",
        "https://example.com ",
        "https://example.com?",
        "https://example.com#",
    ],
)
def test_configuration_rejects_non_origins(settings_data, origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **settings_data, allowed_origins=[origin])


def test_security_configuration_loads_json_environment_and_boolean(
    monkeypatch, settings_data
):
    monkeypatch.setenv(
        "ALLOWED_ORIGINS", '["http://localhost:5173", "https://app.example"]'
    )
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    settings = Settings(_env_file=None, **settings_data)
    assert settings.allowed_origins == ["http://localhost:5173", "https://app.example"]
    assert settings.session_cookie_secure is True


def test_security_configuration_environment_overrides_dotenv(
    tmp_path, monkeypatch, settings_data
):
    path = tmp_path / ".env"
    path.write_text(
        'ALLOWED_ORIGINS=["http://file.example"]\nSESSION_COOKIE_SECURE=false\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("ALLOWED_ORIGINS", '["https://env.example"]')
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    settings = Settings(_env_file=path, **settings_data)
    assert settings.allowed_origins == ["https://env.example"]
    assert settings.session_cookie_secure is True
