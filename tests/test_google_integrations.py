from types import SimpleNamespace
from unittest.mock import mock_open
import datetime
import os
import json

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
        lambda service, version, credentials: SimpleNamespace(spreadsheets=lambda: credentials),
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


def test_sheet_exists_true_and_false():
    sheets = [{"properties": {"title": "One"}}, {"properties": {"title": "Two"}}]

    assert write_to_google_sheet.sheet_exists(sheets, "Two") is True
    assert write_to_google_sheet.sheet_exists(sheets, "Three") is False


def test_delete_all_sheets_returns_early_when_less_than_two(monkeypatch):
    printed = []
    monkeypatch.setattr(
        "builtins.print",
        lambda *args, **kwargs: printed.append(" ".join(str(arg) for arg in args)),
    )

    service = SimpleNamespace(
        get=lambda **kwargs: SimpleNamespace(
            execute=lambda: {"sheets": [{"properties": {"sheetId": 1}}]}
        ),
        batchUpdate=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("batchUpdate should not run")
        ),
    )

    write_to_google_sheet.delete_all_sheets(service)

    assert any("No sheets found." in message for message in printed)


def test_delete_all_sheets_removes_all_but_first_sheet():
    batch_calls = []

    service = SimpleNamespace(
        get=lambda **kwargs: SimpleNamespace(
            execute=lambda: {
                "sheets": [
                    {"properties": {"sheetId": 1}},
                    {"properties": {"sheetId": 2}},
                    {"properties": {"sheetId": 3}},
                ]
            }
        ),
        batchUpdate=lambda **kwargs: (
            batch_calls.append(kwargs) or SimpleNamespace(execute=lambda: {})
        ),
    )

    write_to_google_sheet.delete_all_sheets(service)

    requests = batch_calls[0]["body"]["requests"]
    assert requests == [
        {"deleteSheet": {"sheetId": 2}},
        {"deleteSheet": {"sheetId": 3}},
    ]


def test_google_handles_http_error_when_add_sheet_fails(tmp_path, monkeypatch):
    class FakeHttpError(Exception):
        pass

    payload_file = tmp_path / "positions.json"
    payload_file.write_text(json.dumps({" Team X ": [{"name": "P1", "seasons": []}]}))

    handled = []
    monkeypatch.setattr(write_to_google_sheet.google_api_auth, "HttpError", FakeHttpError)
    monkeypatch.setattr(
        write_to_google_sheet.google_api_auth,
        "sheet_service",
        lambda: SimpleNamespace(
            get=lambda **kwargs: SimpleNamespace(
                execute=lambda: {"sheets": [{"properties": {"title": "Other"}}]}
            ),
            values=lambda: SimpleNamespace(
                update=lambda **kwargs: SimpleNamespace(execute=lambda: {})
            ),
        ),
    )
    monkeypatch.setattr(write_to_google_sheet, "delete_all_sheets", lambda service: None)
    monkeypatch.setattr(
        write_to_google_sheet,
        "add_sheet",
        lambda *args, **kwargs: (_ for _ in ()).throw(FakeHttpError("add failed")),
    )
    monkeypatch.setattr(
        write_to_google_sheet,
        "handle_google_sheets_error",
        lambda err: handled.append(err),
    )

    write_to_google_sheet.google(str(payload_file))

    assert len(handled) == 1


def test_google_handles_http_error_when_values_update_fails(tmp_path, monkeypatch):
    class FakeHttpError(Exception):
        pass

    payload_file = tmp_path / "positions.json"
    payload_file.write_text(json.dumps({" Team X ": [{"name": "P1", "seasons": []}]}))

    handled = []
    monkeypatch.setattr(write_to_google_sheet.google_api_auth, "HttpError", FakeHttpError)
    monkeypatch.setattr(
        write_to_google_sheet.google_api_auth,
        "sheet_service",
        lambda: SimpleNamespace(
            get=lambda **kwargs: SimpleNamespace(
                execute=lambda: {"sheets": [{"properties": {"title": "Team X"}}]}
            ),
            values=lambda: SimpleNamespace(
                update=lambda **kwargs: (_ for _ in ()).throw(FakeHttpError("update failed"))
            ),
        ),
    )
    monkeypatch.setattr(write_to_google_sheet, "delete_all_sheets", lambda service: None)
    monkeypatch.setattr(
        write_to_google_sheet,
        "handle_google_sheets_error",
        lambda err: handled.append(err),
    )

    write_to_google_sheet.google(str(payload_file))

    assert len(handled) == 1


def test_google_handles_http_error_in_final_merge_and_freeze_stage(tmp_path, monkeypatch):
    class FakeHttpError(Exception):
        pass

    payload_file = tmp_path / "positions.json"
    payload_file.write_text(json.dumps({" Team X ": [{"name": "P1", "seasons": []}]}))

    handled = []
    monkeypatch.setattr(write_to_google_sheet.google_api_auth, "HttpError", FakeHttpError)
    monkeypatch.setattr(
        write_to_google_sheet.google_api_auth,
        "sheet_service",
        lambda: SimpleNamespace(
            get=lambda **kwargs: SimpleNamespace(
                execute=lambda: {"sheets": [{"properties": {"title": "Team X", "sheetId": 1}}]}
            ),
            values=lambda: SimpleNamespace(
                update=lambda **kwargs: SimpleNamespace(execute=lambda: {})
            ),
        ),
    )
    monkeypatch.setattr(write_to_google_sheet, "delete_all_sheets", lambda service: None)
    monkeypatch.setattr(write_to_google_sheet, "rename_spreadsheet", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        write_to_google_sheet,
        "handle_merging",
        lambda *args, **kwargs: (_ for _ in ()).throw(FakeHttpError("merge failed")),
    )
    monkeypatch.setattr(write_to_google_sheet, "handle_frozen_row", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        write_to_google_sheet,
        "handle_google_sheets_error",
        lambda err: handled.append(err),
    )

    write_to_google_sheet.google(str(payload_file))

    assert len(handled) == 1


def test_google_success_flow_calls_rename_merge_and_freeze(tmp_path, monkeypatch):
    payload_file = tmp_path / "positions.json"
    payload_file.write_text(json.dumps({" Team X ": [{"name": "P1", "seasons": []}]}))

    calls = {"rename": 0, "merge": 0, "freeze": 0}
    service = SimpleNamespace(
        get=lambda **kwargs: SimpleNamespace(
            execute=lambda: {"sheets": [{"properties": {"title": "Team X", "sheetId": 1}}]}
        ),
        values=lambda: SimpleNamespace(update=lambda **kwargs: SimpleNamespace(execute=lambda: {})),
    )

    monkeypatch.setattr(write_to_google_sheet.google_api_auth, "sheet_service", lambda: service)
    monkeypatch.setattr(write_to_google_sheet, "delete_all_sheets", lambda service_obj: None)
    monkeypatch.setattr(
        write_to_google_sheet,
        "rename_spreadsheet",
        lambda *args, **kwargs: calls.__setitem__("rename", calls["rename"] + 1),
    )
    monkeypatch.setattr(
        write_to_google_sheet,
        "handle_merging",
        lambda *args, **kwargs: calls.__setitem__("merge", calls["merge"] + 1),
    )
    monkeypatch.setattr(
        write_to_google_sheet,
        "handle_frozen_row",
        lambda *args, **kwargs: calls.__setitem__("freeze", calls["freeze"] + 1),
    )

    write_to_google_sheet.google(str(payload_file))

    assert calls == {"rename": 1, "merge": 1, "freeze": 1}


def test_compose_request_body_contains_merge_range_indexes():
    body = write_to_google_sheet.compose_request_body(7, [0, 1, 2, 6], "MERGE_ROWS")

    assert body["mergeCells"]["range"] == {
        "sheetId": 7,
        "startRowIndex": 0,
        "endRowIndex": 1,
        "startColumnIndex": 2,
        "endColumnIndex": 6,
    }
    assert body["mergeCells"]["mergeType"] == "MERGE_ROWS"


def test_get_modification_date_returns_date_from_mtime(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("ok")

    result = write_to_google_sheet.get_modification_date(str(file_path))

    assert isinstance(result, datetime.date)


def test_set_fixed_column_width_handles_success_and_error(monkeypatch):
    class FakeHttpError(Exception):
        pass

    printed = []
    monkeypatch.setattr(
        "builtins.print",
        lambda *args, **kwargs: printed.append(" ".join(str(arg) for arg in args)),
    )
    monkeypatch.setattr(write_to_google_sheet.google_api_auth, "HttpError", FakeHttpError)

    success_service = SimpleNamespace(
        batchUpdate=lambda **kwargs: SimpleNamespace(execute=lambda: {})
    )
    write_to_google_sheet.set_fixed_column_width(success_service, 1, 0, 150)

    failure_service = SimpleNamespace(
        batchUpdate=lambda **kwargs: (_ for _ in ()).throw(FakeHttpError("nope"))
    )
    write_to_google_sheet.set_fixed_column_width(failure_service, 1, 0, 150)

    assert any("width set to 150 pixels" in message for message in printed)
    assert any("Failed to update column width" in message for message in printed)
