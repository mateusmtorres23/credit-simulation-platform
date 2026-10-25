import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILE = REPOSITORY_ROOT / "compose.yaml"
COMPOSE_ENVIRONMENT = {
    "POSTGRES_USER": "compose_test_user",
    "POSTGRES_PASSWORD": "compose_test_password",
    "POSTGRES_DB": "compose_test_db",
    "POSTGRES_PORT": "25432",
    "BANK_A_PORT": "25301",
    "BANK_B_PORT": "25302",
    "CREDIT_API_PORT": "28000",
    "BANK_TIMEOUT_SECONDS": "7",
    "ALLOWED_ORIGINS": '["http://compose.test"]',
    "SESSION_COOKIE_SECURE": "false",
}
INTERPOLATION_VARIABLES = {
    *COMPOSE_ENVIRONMENT,
    "COMPOSE_FILE",
    "COMPOSE_PROFILES",
    "COMPOSE_PROJECT_NAME",
    "COMPOSE_ENV_FILES",
}


def load_compose_config(*, maintenance: bool, monkeypatch: pytest.MonkeyPatch) -> dict:
    with TemporaryDirectory(prefix="compose-config-test-") as directory:
        env_file = Path(directory) / ".env"
        env_file.write_text(
            "\n".join(f"{key}={value}" for key, value in COMPOSE_ENVIRONMENT.items())
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("POSTGRES_USER", "conflicting_process_value")
        environment = {
            key: value
            for key, value in os.environ.items()
            if key not in INTERPOLATION_VARIABLES
        }
        environment["COMPOSE_PROFILES"] = "maintenance" if maintenance else ""
        command = [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "-f",
            str(COMPOSE_FILE),
        ]
        if maintenance:
            command.extend(["--profile", "maintenance"])
        command.extend(["config", "--format", "json"])

        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=environment,
            )
        except FileNotFoundError as error:
            pytest.fail(
                "Docker CLI/Compose plugin is required for Compose integration tests "
                f"but was not found: {error}",
                pytrace=False,
            )
        except subprocess.TimeoutExpired as error:
            pytest.fail(
                f"docker compose config timed out after 30 seconds: {error}",
                pytrace=False,
            )

        if result.returncode != 0:
            output = "\n".join(
                part for part in (result.stdout.strip(), result.stderr.strip()) if part
            )
            pytest.fail(
                f"docker compose config failed with exit code {result.returncode}:\n"
                f"{output or '<no output>'}",
                pytrace=False,
            )
        return json.loads(result.stdout)


def services(config: dict[str, Any]) -> dict[str, Any]:
    return config["services"]


def test_python_image_has_one_build_owner_and_is_reused_by_maintenance_services(
    monkeypatch,
):
    configured_services = services(
        load_compose_config(maintenance=True, monkeypatch=monkeypatch)
    )
    api = configured_services["credit-simulation-api"]

    assert configured_services["postgres"]["environment"]["POSTGRES_USER"] == (
        "compose_test_user"
    )
    assert "build" in api
    assert api["image"] == "credit-simulation-api:local"
    assert configured_services["migrate"].get("build") is None
    assert configured_services["cleanup"].get("build") is None
    assert configured_services["migrate"]["image"] == api["image"]
    assert configured_services["cleanup"]["image"] == api["image"]


def test_maintenance_cleanup_remains_opt_in(monkeypatch):
    configured_services = services(
        load_compose_config(maintenance=False, monkeypatch=monkeypatch)
    )

    assert "cleanup" not in configured_services
