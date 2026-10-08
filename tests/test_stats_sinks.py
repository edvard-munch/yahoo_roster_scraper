from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from roster_scraper.services import stats_sinks


class WorksheetSpy:
    def __init__(self, name):
        self.name = name
        self.columns = []
        self.rows = []

    def set_column(self, *args):
        self.columns.append(args)

    def write_row(self, index, col, row):
        self.rows.append((index, col, list(row)))


class WorkbookSpy:
    def __init__(self):
        self.worksheets = []
        self.closed = False

    def add_worksheet(self, name):
        worksheet = WorksheetSpy(name)
        self.worksheets.append(worksheet)
        return worksheet

    def close(self):
        self.closed = True


class OutputSpy:
    def __init__(self):
        self.calls = []

    def verify_sheet_name(self, name):
        return name.replace("/", "")

    def write_to_xlsx(self, table, worksheet):
        self.calls.append((table, worksheet.name))


def build_sink():
    workbook = WorkbookSpy()
    output = OutputSpy()
    context = SimpleNamespace(
        columns={"first": (0, 0), "second": (1, 1)},
        wide_column_width=25,
    )
    sink = stats_sinks.XlsxStatsSink(workbook, output, context, "MATCHUPS")
    return sink, workbook, output


def test_xlsx_sink_creates_matchups_first_and_writes_team_table():
    sink, workbook, output = build_sink()
    table = {"Team": ["BOS"], "G": [1]}

    sink.write_team("BOS/Stats", table)

    assert [sheet.name for sheet in workbook.worksheets] == ["MATCHUPS", "BOSStats"]
    assert output.calls == [(table, "BOSStats")]


def test_xlsx_sink_writes_matchups_with_existing_layout():
    sink, workbook, _ = build_sink()
    rows = [["Team", "G"], ["Team A", 1.0]]

    sink.write_matchups(rows)

    worksheet = workbook.worksheets[0]
    assert worksheet.columns == [(1, 1, 25), (0, 0, 25)]
    assert worksheet.rows == [
        (0, 0, ["Team", "G"]),
        (1, 0, ["Team A", 1.0]),
    ]


def test_xlsx_sink_closes_workbook():
    sink, workbook, _ = build_sink()

    sink.close()

    assert workbook.closed is True


def test_table_to_rows_transposes_uneven_columns_and_normalizes_none():
    table = {
        "Player": ["Player One", "Player Two"],
        "G": [1, None, 3],
        "GL": [2],
    }

    assert stats_sinks.table_to_rows(table) == [
        ["Player", "G", "GL"],
        ["Player One", 1, 2],
        ["Player Two", "", ""],
        ["", 3, ""],
    ]


def test_google_sheets_sink_writes_teams_matchups_formatting_and_last_run(monkeypatch):
    service = SimpleNamespace()
    values = SimpleNamespace()
    values.batchUpdate = MagicMock(return_value=SimpleNamespace(execute=lambda: {}))
    values.update = MagicMock(return_value=SimpleNamespace(execute=lambda: {}))
    service.values = lambda: values
    service.batchUpdate = MagicMock(return_value=SimpleNamespace(execute=lambda: {}))
    config = stats_sinks.league_sheet_config.LeagueConfig(
        league_id="12922",
        league_name="FNH 26-27",
    )
    team_tabs = [
        stats_sinks.google_sheet_tabs.TeamTab("Team One", "Team One"),
        stats_sinks.google_sheet_tabs.TeamTab("Team/Two", "TeamTwo"),
    ]
    sync_calls = []
    monkeypatch.setattr(
        stats_sinks.google_sheet_tabs,
        "sync_stats_tabs",
        lambda service_arg, spreadsheet_id, team_names: (
            sync_calls.append((service_arg, spreadsheet_id, team_names)) or team_tabs
        ),
    )
    monkeypatch.setattr(
        stats_sinks.google_sheet_tabs,
        "get_sheet_properties",
        lambda service_arg, spreadsheet_id: [
            {"sheetId": 1, "title": "MATCHUPS"},
            {"sheetId": 2, "title": "Team One"},
            {"sheetId": 3, "title": "TeamTwo"},
        ],
    )
    monkeypatch.setattr(
        stats_sinks.league_sheet_config,
        "build_last_run_timestamp",
        lambda: "2026-10-02T17:25:00",
    )

    sink = stats_sinks.GoogleSheetsStatsSink(service, "sheet-123", config)
    sink.write_team("Team One", {"Player": ["A"], "G": [1]})
    sink.write_team("Team/Two", {"Player": ["B"], "G": [2]})
    sink.write_matchups([["Team", "G"], ["Team One", None]])
    sink.close()

    assert sync_calls == [(service, "sheet-123", ["Team One", "Team/Two"])]
    values.batchUpdate.assert_called_once_with(
        spreadsheetId="sheet-123",
        body={
            "valueInputOption": "RAW",
            "data": [
                {
                    "range": "'Team One'",
                    "values": [["Player", "G"], ["A", 1]],
                },
                {
                    "range": "'TeamTwo'",
                    "values": [["Player", "G"], ["B", 2]],
                },
                {
                    "range": "'MATCHUPS'",
                    "values": [["Team", "G"], ["Team One", ""]],
                },
            ],
        },
    )
    requests = service.batchUpdate.call_args.kwargs["body"]["requests"]
    assert len(requests) == 6
    assert requests[0]["updateSheetProperties"]["properties"]["sheetId"] == 1
    assert requests[1]["updateDimensionProperties"]["range"] == {
        "sheetId": 1,
        "dimension": "COLUMNS",
        "startIndex": 0,
        "endIndex": 2,
    }
    assert requests[3]["updateDimensionProperties"]["range"]["startIndex"] == 1
    assert config.last_run == "2026-10-02T17:25:00"
    values.update.assert_called_once_with(
        spreadsheetId="sheet-123",
        range="_config",
        valueInputOption="RAW",
        body={"values": stats_sinks.league_sheet_config.config_to_rows(config)},
    )


def test_google_sheets_sink_empty_close_skips_values_and_is_idempotent(monkeypatch):
    service = MagicMock()
    config = stats_sinks.league_sheet_config.LeagueConfig(league_id="12922")
    monkeypatch.setattr(
        stats_sinks.google_sheet_tabs,
        "sync_stats_tabs",
        lambda service_arg, spreadsheet_id, team_names: [],
    )
    monkeypatch.setattr(
        stats_sinks.google_sheet_tabs,
        "get_sheet_properties",
        lambda service_arg, spreadsheet_id: [{"sheetId": 1, "title": "MATCHUPS"}],
    )
    monkeypatch.setattr(
        stats_sinks.league_sheet_config,
        "build_last_run_timestamp",
        lambda: "2026-10-02T17:25:00",
    )

    sink = stats_sinks.GoogleSheetsStatsSink(service, "sheet-123", config)
    sink.close()
    sink.close()

    service.values.return_value.batchUpdate.assert_not_called()
    service.batchUpdate.assert_called_once()
    service.values.return_value.update.assert_called_once()


def test_google_sheets_sink_rejects_writes_after_close(monkeypatch):
    service = MagicMock()
    monkeypatch.setattr(
        stats_sinks.google_sheet_tabs,
        "sync_stats_tabs",
        lambda service_arg, spreadsheet_id, team_names: [],
    )
    monkeypatch.setattr(
        stats_sinks.google_sheet_tabs,
        "get_sheet_properties",
        lambda service_arg, spreadsheet_id: [{"sheetId": 1, "title": "MATCHUPS"}],
    )
    sink = stats_sinks.GoogleSheetsStatsSink(
        service,
        "sheet-123",
        stats_sinks.league_sheet_config.LeagueConfig(league_id="12922"),
    )
    sink.close()

    with pytest.raises(RuntimeError, match="closed Google Sheets"):
        sink.write_team("Team", {})


def test_google_sheets_sink_does_not_update_config_after_value_write_failure(monkeypatch):
    service = MagicMock()
    error = RuntimeError("Google write failed")
    service.values.return_value.batchUpdate.return_value.execute.side_effect = error
    config = stats_sinks.league_sheet_config.LeagueConfig(league_id="12922")
    monkeypatch.setattr(
        stats_sinks.google_sheet_tabs,
        "sync_stats_tabs",
        lambda service_arg, spreadsheet_id, team_names: [
            stats_sinks.google_sheet_tabs.TeamTab("Team", "Team")
        ],
    )

    sink = stats_sinks.GoogleSheetsStatsSink(service, "sheet-123", config)
    sink.write_team("Team", {"G": [1]})

    with pytest.raises(RuntimeError, match="Google write failed"):
        sink.close()

    assert config.last_run is None
    service.values.return_value.update.assert_not_called()


def test_google_sheets_sink_restores_last_run_when_config_write_fails(monkeypatch):
    service = MagicMock()
    config = stats_sinks.league_sheet_config.LeagueConfig(
        league_id="12922",
        last_run="previous-run",
    )
    monkeypatch.setattr(
        stats_sinks.google_sheet_tabs,
        "sync_stats_tabs",
        lambda service_arg, spreadsheet_id, team_names: [],
    )
    monkeypatch.setattr(
        stats_sinks.google_sheet_tabs,
        "get_sheet_properties",
        lambda service_arg, spreadsheet_id: [{"sheetId": 1, "title": "MATCHUPS"}],
    )
    monkeypatch.setattr(
        stats_sinks.league_sheet_config,
        "build_last_run_timestamp",
        lambda: "new-run",
    )
    monkeypatch.setattr(
        stats_sinks.league_sheet_config,
        "write_league_config",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("config write failed")),
    )
    sink = stats_sinks.GoogleSheetsStatsSink(service, "sheet-123", config)

    with pytest.raises(RuntimeError, match="config write failed"):
        sink.close()

    assert config.last_run == "previous-run"
    assert sink.closed is False
