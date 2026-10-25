import sys
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app import cleanup


@pytest.fixture(autouse=True)
def command_arguments(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cleanup"])


def test_command_prints_only_committed_count(monkeypatch, capsys):
    settings = object()
    monkeypatch.setattr(cleanup, "Settings", lambda: settings)
    run = AsyncMock(return_value=3)
    monkeypatch.setattr(cleanup, "run_cleanup", run)
    assert cleanup.main() == 0
    run.assert_awaited_once_with(settings)
    assert capsys.readouterr().out == "Sessões expiradas removidas: 3.\n"


@pytest.mark.parametrize(
    "failure",
    [
        SQLAlchemyError("private-database-details"),
        OSError("private-os-details"),
        ValidationError.from_exception_data(
            "Settings",
            [
                {
                    "type": "missing",
                    "loc": ("postgres_password",),
                    "input": "private-input",
                }
            ],
        ),
    ],
)
def test_command_failure_has_nonzero_exit_and_safe_message(
    monkeypatch, capsys, failure
):
    monkeypatch.setattr(cleanup, "Settings", lambda: object())
    monkeypatch.setattr(cleanup, "run_cleanup", AsyncMock(side_effect=failure))
    assert cleanup.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "Não foi possível concluir a limpeza" in output.err
    assert "private-" not in output.err


def test_interruption_returns_conventional_exit_code(monkeypatch):
    monkeypatch.setattr(cleanup, "Settings", lambda: object())
    monkeypatch.setattr(
        cleanup, "run_cleanup", AsyncMock(side_effect=KeyboardInterrupt())
    )
    assert cleanup.main() == 130


def test_help_does_not_load_settings_or_connect(monkeypatch):
    settings = Mock(side_effect=AssertionError("Must not load settings"))
    monkeypatch.setattr(cleanup, "Settings", settings)
    monkeypatch.setattr(sys, "argv", ["cleanup", "--help"])
    with pytest.raises(SystemExit) as error:
        cleanup.main()
    assert error.value.code == 0
    settings.assert_not_called()
