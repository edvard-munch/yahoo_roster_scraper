from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from fastapi.testclient import TestClient
from google.auth.exceptions import DefaultCredentialsError
from googleapiclient.errors import HttpError

from roster_scraper import web
from roster_scraper.services import google_sheet_runner, sheet_run_config


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv(web.API_SECRET_ENV, "test-secret")
    calls = []
    app = web.create_app()
    app.dependency_overrides[web.get_scrape_runner] = lambda: calls.append
    with TestClient(app) as client:
        yield client, app, calls


def auth_headers():
    return {"Authorization": "Bearer test-secret"}


def test_health_does_not_require_credentials_or_secret(api, monkeypatch):
    client, _, calls = api
    monkeypatch.delenv(web.API_SECRET_ENV)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert calls == []


@pytest.mark.parametrize("secret", [None, "", "   "])
def test_scrape_fails_closed_when_secret_is_not_configured(api, monkeypatch, secret):
    client, _, calls = api
    if secret is None:
        monkeypatch.delenv(web.API_SECRET_ENV)
    else:
        monkeypatch.setenv(web.API_SECRET_ENV, secret)

    response = client.post("/scrape", headers=auth_headers(), json={"spreadsheet_id": "sheet-123"})

    assert response.status_code == 503
    assert calls == []


@pytest.mark.parametrize(
    "authorization", [None, "Bearer incorrect", "Basic test-secret", "Bearer", "Bearer ü"]
)
def test_invalid_authentication_does_not_run_scraper(api, authorization):
    client, _, calls = api
    headers = {"Authorization": authorization} if authorization else {}
    # HTTP headers with non-ASCII content must be supplied as encoded bytes.
    if authorization == "Bearer ü":
        headers = {"Authorization": authorization.encode("utf-8")}

    response = client.post("/scrape", headers=headers, json={"spreadsheet_id": "sheet-123"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"spreadsheet_id": ""},
        {"spreadsheet_id": None},
        {"spreadsheet_id": 123},
        {"spreadsheet_id": "https://docs.google.com/spreadsheets/d/id"},
        {"spreadsheet_id": "id with spaces"},
        {"spreadsheet_id": "a" * 257},
        {"spreadsheet_id": "sheet-123", "league_id": "override-not-allowed"},
    ],
)
def test_malformed_payload_fails_before_scraping(api, payload):
    client, _, calls = api

    response = client.post("/scrape", headers=auth_headers(), json=payload)

    assert response.status_code == 422
    assert calls == []


def test_scrape_returns_success_only_after_runner_returns(api):
    client, _, calls = api

    response = client.post(
        "/scrape", headers=auth_headers(), json={"spreadsheet_id": "sheet-123_A"}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "complete", "spreadsheet_id": "sheet-123_A"}
    assert calls == ["sheet-123_A"]


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (
            sheet_run_config.SheetConfigError("Invalid _config season"),
            422,
            "Invalid _config season",
        ),
        (
            google_sheet_runner.LeaguePreparationError("private detail"),
            502,
            "Could not prepare the Yahoo league",
        ),
        (DefaultCredentialsError("private detail"), 503, "Google authentication unavailable"),
        (requests.ConnectionError("private detail"), 502, "Upstream scraper request failed"),
        (RuntimeError("private detail"), 500, "Scraper run failed"),
    ],
)
def test_runner_errors_have_safe_http_responses(api, caplog, error, status, detail):
    client, app, _ = api

    def fail(spreadsheet_id):
        raise error

    app.dependency_overrides[web.get_scrape_runner] = lambda: fail
    response = client.post("/scrape", headers=auth_headers(), json={"spreadsheet_id": "sheet-123"})

    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert "private detail" not in response.text
    assert "private detail" not in caplog.text
    assert "test-secret" not in caplog.text


def test_google_api_failure_does_not_expose_upstream_body(api, caplog):
    client, app, _ = api
    error = HttpError(
        SimpleNamespace(status=403, reason="Forbidden"),
        b'{"error": {"message": "private detail"}}',
        uri="https://example.com/?credential=private",
    )

    def fail(spreadsheet_id):
        raise error

    app.dependency_overrides[web.get_scrape_runner] = lambda: fail
    response = client.post("/scrape", headers=auth_headers(), json={"spreadsheet_id": "sheet-123"})

    assert response.status_code == 502
    assert response.json() == {"detail": "Google Sheets request failed"}
    assert "private" not in response.text
    assert "private" not in caplog.text


def test_default_runner_uses_adc_and_injected_runtime_without_browser(monkeypatch):
    sheets = object()
    dependencies = object()
    context = object()
    run = Mock(return_value="proxy-result")
    monkeypatch.setattr(web.google_api_auth, "cloud_sheet_service", lambda: sheets)
    monkeypatch.setattr(web.runtime, "build_default_sheet_runtime", lambda: (dependencies, context))
    monkeypatch.setattr(web.google_sheet_runner, "run_google_sheet_scrape", run)
    monkeypatch.setattr(
        web.google_api_auth,
        "get_credentials",
        lambda: (_ for _ in ()).throw(AssertionError("No installed-app OAuth")),
    )
    monkeypatch.setattr(
        "builtins.input",
        lambda *args: (_ for _ in ()).throw(AssertionError("No interactive prompts")),
    )

    assert web.run_scraper("sheet-123") == "proxy-result"
    run.assert_called_once_with(sheets, "sheet-123", dependencies, context)
