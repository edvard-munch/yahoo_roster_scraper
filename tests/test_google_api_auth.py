from types import SimpleNamespace
from unittest.mock import mock_open

from roster_scraper.services import google_api_auth


def test_sheet_service_runs_oauth_flow_when_token_is_missing(monkeypatch):
    fresh_creds = SimpleNamespace(valid=True, has_scopes=lambda scopes: True)
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

    creds = SimpleNamespace(valid=False, refresh=refresh, has_scopes=lambda scopes: True)
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


def test_get_credentials_requires_consent_when_cached_scopes_are_missing(monkeypatch):
    stale_creds = SimpleNamespace(
        valid=True,
        has_scopes=lambda scopes: False,
        refresh=lambda request: (_ for _ in ()).throw(AssertionError("Refresh cannot add scopes")),
    )
    fresh_creds = SimpleNamespace(valid=True, has_scopes=lambda scopes: True)
    scope_requests = []
    dumped = []
    monkeypatch.setattr(google_api_auth.os.path, "exists", lambda path: True)
    monkeypatch.setattr("builtins.open", mock_open())
    monkeypatch.setattr(google_api_auth.pickle, "load", lambda token: stale_creds)
    monkeypatch.setattr(google_api_auth.pickle, "dump", lambda creds, token: dumped.append(creds))
    monkeypatch.setattr(
        google_api_auth.InstalledAppFlow,
        "from_client_secrets_file",
        lambda filename, scopes: (
            scope_requests.append(scopes)
            or SimpleNamespace(run_local_server=lambda port: fresh_creds)
        ),
    )

    assert google_api_auth.get_credentials() is fresh_creds
    assert scope_requests == [google_api_auth.SCOPES]
    assert "https://www.googleapis.com/auth/drive.file" in scope_requests[0]
    assert dumped == [fresh_creds]


def test_drive_service_builds_files_client_with_shared_credentials(monkeypatch):
    creds = object()
    calls = []
    monkeypatch.setattr(google_api_auth, "get_credentials", lambda: creds)
    monkeypatch.setattr(
        google_api_auth,
        "build",
        lambda service, version, credentials: (
            calls.append((service, version, credentials))
            or SimpleNamespace(files=lambda: "drive-files-client")
        ),
    )

    assert google_api_auth.drive_service() == "drive-files-client"
    assert calls == [("drive", "v3", creds)]


def test_cloud_sheet_service_uses_adc_with_sheets_only_scope(monkeypatch):
    credentials = object()
    adc_calls = []
    build_calls = []
    monkeypatch.setattr(
        google_api_auth.google.auth,
        "default",
        lambda **kwargs: adc_calls.append(kwargs) or (credentials, "cloud-project"),
    )
    monkeypatch.setattr(
        google_api_auth,
        "build",
        lambda service, version, credentials: (
            build_calls.append((service, version, credentials))
            or SimpleNamespace(spreadsheets=lambda: "cloud-sheets-client")
        ),
    )

    assert google_api_auth.cloud_sheet_service() == "cloud-sheets-client"
    assert adc_calls == [{"scopes": ["https://www.googleapis.com/auth/spreadsheets"]}]
    assert build_calls == [("sheets", "v4", credentials)]


def test_cloud_sheet_service_does_not_use_local_oauth_or_token_files(monkeypatch):
    credentials = object()

    def forbidden(*args, **kwargs):
        raise AssertionError("Cloud auth must not use local OAuth or token files")

    monkeypatch.setattr(
        google_api_auth.google.auth,
        "default",
        lambda **kwargs: (credentials, None),
    )
    monkeypatch.setattr(google_api_auth, "get_credentials", forbidden)
    monkeypatch.setattr(google_api_auth.InstalledAppFlow, "from_client_secrets_file", forbidden)
    monkeypatch.setattr(google_api_auth.pickle, "load", forbidden)
    monkeypatch.setattr(google_api_auth.pickle, "dump", forbidden)
    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr(
        google_api_auth,
        "build",
        lambda *args, **kwargs: SimpleNamespace(spreadsheets=lambda: credentials),
    )

    assert google_api_auth.cloud_sheet_service() is credentials


def test_cloud_sheet_service_propagates_missing_adc_without_oauth_fallback(monkeypatch):
    import pytest
    from google.auth.exceptions import DefaultCredentialsError

    error = DefaultCredentialsError("No application default credentials")
    build_calls = []

    def missing_adc(**kwargs):
        raise error

    monkeypatch.setattr(google_api_auth.google.auth, "default", missing_adc)
    monkeypatch.setattr(google_api_auth, "build", lambda *args, **kwargs: build_calls.append(args))
    monkeypatch.setattr(
        google_api_auth,
        "get_credentials",
        lambda: (_ for _ in ()).throw(AssertionError("No local OAuth fallback in cloud mode")),
    )

    with pytest.raises(DefaultCredentialsError) as caught:
        google_api_auth.cloud_sheet_service()

    assert caught.value is error
    assert build_calls == []


def test_cloud_sheet_service_propagates_client_creation_errors(monkeypatch):
    import pytest

    error = RuntimeError("Sheets client creation failed")
    monkeypatch.setattr(google_api_auth.google.auth, "default", lambda **kwargs: (object(), None))
    monkeypatch.setattr(
        google_api_auth,
        "build",
        lambda *args, **kwargs: (_ for _ in ()).throw(error),
    )

    with pytest.raises(RuntimeError) as caught:
        google_api_auth.cloud_sheet_service()

    assert caught.value is error
