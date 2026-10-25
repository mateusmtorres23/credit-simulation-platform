import pytest
from pydantic import ValidationError

from app.config import Settings


def test_dotenv_loading_and_environment_precedence(
    tmp_path, monkeypatch, settings_data
):
    path = tmp_path / ".env"
    path.write_text(
        "\n".join(f"{key.upper()}={value}" for key, value in settings_data.items()),
        encoding="utf-8",
    )
    assert Settings(_env_file=path).postgres_user == "test_user"
    monkeypatch.setenv("POSTGRES_USER", "override")
    assert Settings(_env_file=path).postgres_user == "override"


@pytest.mark.parametrize(
    "field",
    [
        "postgres_user",
        "postgres_password",
        "postgres_db",
        "postgres_host",
        "postgres_port",
    ],
)
def test_required_fields(field, settings_data):
    del settings_data[field]
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, **settings_data)
    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize(
    "field,value",
    [
        ("postgres_user", " \t"),
        ("postgres_db", ""),
        ("postgres_host", "\n"),
        ("postgres_password", ""),
        ("postgres_port", 0),
        ("postgres_port", 65536),
        ("postgres_port", "invalid"),
    ],
)
def test_invalid_settings(field, value, settings_data):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **(settings_data | {field: value}))


@pytest.mark.parametrize("port", [1, 65535])
def test_port_boundaries(port, settings_data):
    assert (
        Settings(
            _env_file=None, **(settings_data | {"postgres_port": port})
        ).postgres_port
        == port
    )


def test_password_is_hidden_in_representations(settings_data):
    settings = Settings(_env_file=None, **settings_data)
    assert settings_data["postgres_password"] not in repr(settings)
    assert settings_data["postgres_password"] not in settings.model_dump_json()
    with pytest.raises(ValidationError) as error:
        Settings(
            _env_file=None,
            **(settings_data | {"postgres_port": "private-invalid-value"}),
        )
    assert "private-invalid-value" not in str(error.value)
