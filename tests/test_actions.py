import argparse
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.auth.exceptions import DefaultCredentialsError
from googleapiclient.errors import HttpError

from roster_scraper import actions
from roster_scraper.services import google_sheet_runner, sheet_run_config


@pytest.mark.parametrize(
    "spreadsheet_id",
    ["", "id with spaces", "https://docs.google.com/spreadsheets/d/id", "a" * 257, "id\n"],
)
def test_invalid_spreadsheet_id_is_rejected(spreadsheet_id):
    with pytest.raises(argparse.ArgumentTypeError):
        actions.parse_spreadsheet_id(spreadsheet_id)


def test_valid_spreadsheet_id_is_returned():
    assert actions.parse_spreadsheet_id("sheet-123_A") == "sheet-123_A"


@pytest.mark.parametrize("arguments", [[], ["--spreadsheet-id", "invalid url"], ["--unknown"]])
def test_invalid_arguments_fail_before_any_scraping(monkeypatch, arguments):
    runner = Mock()
    monkeypatch.setattr(actions, "run_actions_scrape", runner)

    with pytest.raises(SystemExit) as error:
        actions.main(arguments)

    assert error.value.code == 2
    runner.assert_not_called()


def test_command_runs_once_and_reports_success(monkeypatch, capsys):
    runner = Mock(return_value=None)
    monkeypatch.setattr(actions, "run_actions_scrape", runner)

    assert actions.main(["--spreadsheet-id", "sheet-123_A"]) == actions.EXIT_SUCCESS

    runner.assert_called_once_with("sheet-123_A")
    output = capsys.readouterr()
    assert "Stats refresh complete for spreadsheet sheet-123_A." in output.out
    assert output.err == ""


@pytest.mark.parametrize(
    ("error", "expected_message"),
    [
        (DefaultCredentialsError("private-secret"), "ADC authentication failed"),
        (
            HttpError(
                SimpleNamespace(status=403, reason="Forbidden"),
                b'{"error": {"message": "private-secret"}}',
            ),
            "Google Sheets request failed",
        ),
        (sheet_run_config.SheetConfigError("private-secret"), "Invalid _config"),
        (google_sheet_runner.LeaguePreparationError("private-secret"), "Could not prepare"),
        (RuntimeError("private-secret"), "Scraper run failed"),
    ],
)
def test_command_failure_returns_nonzero_without_exposing_error(
    monkeypatch, capsys, error, expected_message
):
    monkeypatch.setattr(actions, "run_actions_scrape", Mock(side_effect=error))

    assert actions.main(["--spreadsheet-id", "sheet-123"]) == actions.EXIT_FAILURE

    output = capsys.readouterr()
    assert expected_message in output.err
    assert "private-secret" not in output.err
    assert "Traceback" not in output.err
    assert "complete" not in output.out


def test_job_runner_uses_adc_and_existing_sheet_runner_without_interaction(monkeypatch):
    service = object()
    dependencies = object()
    context = object()
    runner = Mock()
    monkeypatch.setattr(actions.google_api_auth, "cloud_sheet_service", lambda: service)
    monkeypatch.setattr(
        actions.runtime, "build_default_sheet_runtime", lambda: (dependencies, context)
    )
    monkeypatch.setattr(actions.google_sheet_runner, "run_google_sheet_scrape", runner)

    def forbidden(*args, **kwargs):
        raise AssertionError("Job entrypoint must not use prompts or installed-app OAuth")

    monkeypatch.setattr("builtins.input", forbidden)
    monkeypatch.setattr(actions.google_api_auth, "get_credentials", forbidden)
    monkeypatch.setattr(
        actions.google_api_auth.InstalledAppFlow, "from_client_secrets_file", forbidden
    )

    actions.run_actions_scrape("sheet-123")

    runner.assert_called_once_with(service, "sheet-123", dependencies, context)


def test_module_help_works_without_credentials_or_cli_import():
    source = """
import importlib.abc
import runpy
import sys
class NoCli(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "roster_scraper.cli":
            raise AssertionError("Actions must not import the interactive CLI")
sys.meta_path.insert(0, NoCli())
sys.argv = ["roster_scraper.actions", "--help"]
runpy.run_module("roster_scraper.actions", run_name="__main__")
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "--spreadsheet-id" in result.stdout
