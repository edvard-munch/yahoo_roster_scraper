from types import SimpleNamespace
from unittest.mock import mock_open

from roster_scraper.services import google_api_auth


def test_sheet_service_runs_oauth_flow_when_token_is_missing(monkeypatch):
    fresh_creds = SimpleNamespace(valid=True)
    flow = SimpleNamespace(run_local_server=lambda port: fresh_creds)
    dumped = {}

    monkeypatch.setattr(google_api_auth.os.path, "exists", lambda path: False)
    monkeypatch.setattr("builtins.open", mock_open())
    monkeypatch.setattr(
        google_api_auth.InstalledAppFlow,
        "from_client_secrets_file",
        lambda credentials_file, scopes: flow,
    )
    monkeypatch.setattr(
        google_api_auth.pickle,
        "dump",
        lambda creds, token_file: dumped.update({"creds": creds}),
    )
    monkeypatch.setattr(
        google_api_auth,
        "build",
        lambda service, version, credentials: SimpleNamespace(spreadsheets=lambda: credentials),
    )

    result = google_api_auth.sheet_service()

    assert result is fresh_creds
    assert dumped["creds"] is fresh_creds


def test_sheet_service_refreshes_invalid_token_without_oauth(monkeypatch):
    refresh_calls = {"count": 0}

    def refresh(_request):
        refresh_calls["count"] += 1
        creds.valid = True

    creds = SimpleNamespace(valid=False, refresh=refresh)
    dumped = {}

    monkeypatch.setattr(google_api_auth.os.path, "exists", lambda path: True)
    monkeypatch.setattr("builtins.open", mock_open())
    monkeypatch.setattr(google_api_auth.pickle, "load", lambda token_file: creds)
    monkeypatch.setattr(google_api_auth, "Request", lambda: "request")
    monkeypatch.setattr(
        google_api_auth.pickle,
        "dump",
        lambda creds_obj, token_file: dumped.update({"creds": creds_obj}),
    )
    monkeypatch.setattr(
        google_api_auth.InstalledAppFlow,
        "from_client_secrets_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("OAuth flow should not be used when refresh succeeds")
        ),
    )
    monkeypatch.setattr(
        google_api_auth,
        "build",
        lambda service, version, credentials: SimpleNamespace(spreadsheets=lambda: credentials),
    )

    result = google_api_auth.sheet_service()

    assert result is creds
    assert refresh_calls["count"] == 1
    assert dumped["creds"] is creds
