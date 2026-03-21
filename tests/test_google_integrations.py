from types import SimpleNamespace
from unittest.mock import mock_open

from google.auth import exceptions

from roster_scraper.services import google_api_auth
from roster_scraper.services import write_to_google_sheet


def test_sheet_service_returns_spreadsheets_client_with_valid_token(monkeypatch):
    creds = SimpleNamespace(valid=True)

    monkeypatch.setattr(google_api_auth.os.path, "exists", lambda path: True)
    monkeypatch.setattr("builtins.open", mock_open())
    monkeypatch.setattr(google_api_auth.pickle, "load", lambda token_file: creds)
    monkeypatch.setattr(
        google_api_auth,
        "build",
        lambda service, version, credentials: SimpleNamespace(
            spreadsheets=lambda: "sheets-service"
        ),
    )

    result = google_api_auth.sheet_service()

    assert result == "sheets-service"


def test_sheet_service_runs_oauth_flow_when_refresh_fails(monkeypatch):
    def raise_refresh_error(_request):
        raise exceptions.RefreshError("expired")

    stale_creds = SimpleNamespace(valid=False, refresh=raise_refresh_error)
    fresh_creds = SimpleNamespace(valid=True)
    flow = SimpleNamespace(run_local_server=lambda port: fresh_creds)

    dumped = {}

    monkeypatch.setattr(google_api_auth.os.path, "exists", lambda path: True)
    monkeypatch.setattr("builtins.open", mock_open())
    monkeypatch.setattr(google_api_auth.pickle, "load", lambda token_file: stale_creds)
    monkeypatch.setattr(
        google_api_auth.pickle,
        "dump",
        lambda creds, token_file: dumped.update({"creds": creds}),
    )
    monkeypatch.setattr(
        google_api_auth.InstalledAppFlow,
        "from_client_secrets_file",
        lambda credentials_file, scopes: flow,
    )
    monkeypatch.setattr(google_api_auth, "Request", lambda: "request")
    monkeypatch.setattr(
        google_api_auth,
        "build",
        lambda service, version, credentials: SimpleNamespace(
            spreadsheets=lambda: credentials
        ),
    )

    result = google_api_auth.sheet_service()

    assert result is fresh_creds
    assert dumped["creds"] is fresh_creds


def test_handle_google_sheets_error_prints_forbidden_details(monkeypatch):
    printed = []
    monkeypatch.setattr(
        "builtins.print",
        lambda *args, **kwargs: printed.append(" ".join(str(arg) for arg in args)),
    )
    monkeypatch.setattr(write_to_google_sheet, "SPREADSHEET_ID", "sheet-123")

    error = SimpleNamespace(resp=SimpleNamespace(status=403))

    write_to_google_sheet.handle_google_sheets_error(error)

    assert any("403 Forbidden" in message for message in printed)
    assert any("sheet-123" in message for message in printed)


def test_google_handles_http_error_on_initial_fetch(monkeypatch):
    class FakeHttpError(Exception):
        pass

    handled = []

    monkeypatch.setattr(
        write_to_google_sheet.google_api_auth,
        "sheet_service",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        write_to_google_sheet.google_api_auth,
        "HttpError",
        FakeHttpError,
    )
    monkeypatch.setattr(
        write_to_google_sheet,
        "delete_all_sheets",
        lambda service: (_ for _ in ()).throw(FakeHttpError("boom")),
    )
    monkeypatch.setattr(
        write_to_google_sheet,
        "handle_google_sheets_error",
        lambda err: handled.append(err),
    )

    write_to_google_sheet.google("unused.json")

    assert len(handled) == 1
