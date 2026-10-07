from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from roster_scraper.services import league_sheet_config, league_spreadsheets


def make_services():
    sheets = MagicMock()
    drive = MagicMock()
    drive.list.return_value.execute.return_value = {"files": []}
    sheets.create.return_value.execute.return_value = {"spreadsheetId": "stats-123"}
    sheets.get.return_value.execute.return_value = {
        "spreadsheetId": "stats-123",
        "properties": {"title": "FNH 26-27 Stats"},
        "sheets": [],
    }
    sheets.values.return_value.get.return_value.execute.return_value = {
        "values": [["league_id", "12922"], ["last_run", "2026-10-02T17:00:00"]]
    }
    return sheets, drive


def test_create_spreadsheet_initializes_config_and_empty_matchups():
    sheets, drive = make_services()
    config = league_sheet_config.LeagueConfig(
        league_id="12922", league_name="FNH 26-27", season="preseason"
    )

    spreadsheet_id = league_spreadsheets.create_spreadsheet(sheets, drive, config)

    assert spreadsheet_id == "stats-123"
    sheets.create.assert_called_once_with(
        body={
            "properties": {"title": "FNH 26-27 Stats"},
            "sheets": [
                {"properties": {"title": "MATCHUPS"}},
                {"properties": {"title": "_config", "hidden": True}},
            ],
        },
        fields="spreadsheetId",
    )
    drive.update.assert_called_once_with(
        fileId="stats-123",
        body={"appProperties": {"roster_scraper": "league_stats", "league_id": "12922"}},
        fields="id",
    )
    sheets.values.return_value.update.assert_called_once_with(
        spreadsheetId="stats-123",
        range="_config",
        valueInputOption="RAW",
        body={"values": league_sheet_config.config_to_rows(config)},
    )


def test_resolve_creates_once_then_reuses_without_overwriting_config():
    sheets, drive = make_services()
    drive.list.return_value.execute.side_effect = [
        {"files": []},
        {"files": [{"id": "stats-123"}]},
    ]
    config = league_sheet_config.LeagueConfig(
        league_id="12922", league_name="FNH 26-27", season="preseason"
    )

    first = league_spreadsheets.resolve_league_spreadsheet(sheets, drive, config)
    second = league_spreadsheets.resolve_league_spreadsheet(sheets, drive, config)

    assert first == second == "stats-123"
    sheets.create.assert_called_once()
    sheets.values.return_value.update.assert_called_once()
    sheets.get.assert_called_once_with(
        spreadsheetId="stats-123",
        fields="spreadsheetId,spreadsheetUrl,properties.title,sheets.properties",
    )


def test_discovery_uses_private_league_metadata_not_file_title():
    _, drive = make_services()

    assert league_spreadsheets.find_league_spreadsheet(drive, "12922") is None

    query = drive.list.call_args.kwargs["q"]
    assert "trashed = false" in query
    assert "mimeType = 'application/vnd.google-apps.spreadsheet'" in query
    assert "key='roster_scraper' value='league_stats'" in query
    assert "key='league_id' value='12922'" in query
    assert "name =" not in query


def test_discovery_follows_pagination():
    _, drive = make_services()
    drive.list.return_value.execute.side_effect = [
        {"files": [], "nextPageToken": "next-page"},
        {"files": [{"id": "stats-123"}]},
    ]

    assert league_spreadsheets.find_league_spreadsheet(drive, "12922") == "stats-123"
    assert drive.list.call_args_list[1].kwargs["pageToken"] == "next-page"


def test_duplicate_spreadsheets_are_reported_without_creating_another():
    sheets, drive = make_services()
    drive.list.return_value.execute.return_value = {"files": [{"id": "first"}, {"id": "second"}]}

    with pytest.raises(ValueError, match="Multiple stats spreadsheets"):
        league_spreadsheets.resolve_league_spreadsheet(
            sheets, drive, league_sheet_config.LeagueConfig(league_id="12922")
        )

    sheets.create.assert_not_called()


def test_mismatched_config_is_reported_without_replacing_spreadsheet():
    sheets, drive = make_services()
    drive.list.return_value.execute.return_value = {"files": [{"id": "stats-123"}]}
    sheets.values.return_value.get.return_value.execute.return_value = {
        "values": [["league_id", "other-league"]]
    }

    with pytest.raises(ValueError, match="missing or mismatched league config"):
        league_spreadsheets.resolve_league_spreadsheet(
            sheets, drive, league_sheet_config.LeagueConfig(league_id="12922")
        )

    sheets.create.assert_not_called()
    sheets.values.return_value.update.assert_not_called()


def test_api_permission_error_propagates_without_creating_a_duplicate():
    sheets, drive = make_services()
    error = HttpError(MagicMock(status=403, reason="Forbidden"), b'{"error": "Forbidden"}')
    drive.list.return_value.execute.side_effect = error

    with pytest.raises(HttpError):
        league_spreadsheets.resolve_league_spreadsheet(
            sheets, drive, league_sheet_config.LeagueConfig(league_id="12922")
        )

    sheets.create.assert_not_called()


@pytest.mark.parametrize("league_id", ["", "12' OR '1", "abc", "１２", None, 12922])
def test_invalid_league_id_does_not_call_google(league_id):
    sheets, drive = make_services()

    with pytest.raises(ValueError, match="League ID"):
        league_spreadsheets.resolve_league_spreadsheet(
            sheets, drive, league_sheet_config.LeagueConfig(league_id=league_id)
        )

    drive.list.assert_not_called()
    sheets.create.assert_not_called()


def test_existing_spreadsheet_fetch_error_does_not_create_replacement():
    sheets, drive = make_services()
    drive.list.return_value.execute.return_value = {"files": [{"id": "stats-123"}]}
    error = HttpError(MagicMock(status=404, reason="Not Found"), b'{"error": "Not Found"}')
    sheets.get.return_value.execute.side_effect = error

    with pytest.raises(HttpError):
        league_spreadsheets.resolve_league_spreadsheet(
            sheets, drive, league_sheet_config.LeagueConfig(league_id="12922")
        )

    sheets.create.assert_not_called()


def test_duplicate_matches_across_pages_are_reported():
    _, drive = make_services()
    drive.list.return_value.execute.side_effect = [
        {"files": [{"id": "first"}], "nextPageToken": "next-page"},
        {"files": [{"id": "second"}]},
    ]

    with pytest.raises(ValueError, match="Multiple stats spreadsheets"):
        league_spreadsheets.find_league_spreadsheet(drive, "12922")


def test_create_spreadsheet_falls_back_to_league_id_when_name_is_missing():
    sheets, drive = make_services()
    config = league_sheet_config.LeagueConfig(league_id="12922")

    league_spreadsheets.create_spreadsheet(sheets, drive, config)

    body = sheets.create.call_args.kwargs["body"]
    assert body["properties"]["title"] == "Yahoo Hockey League 12922 Stats"


def test_resolve_renames_existing_spreadsheet_when_league_name_changes():
    sheets, drive = make_services()
    drive.list.return_value.execute.return_value = {"files": [{"id": "stats-123"}]}
    sheets.get.return_value.execute.return_value["properties"]["title"] = "Old League Name Stats"
    config = league_sheet_config.LeagueConfig(
        league_id="12922", league_name="FNH 26-27", season="preseason"
    )

    spreadsheet_id = league_spreadsheets.resolve_league_spreadsheet(sheets, drive, config)

    assert spreadsheet_id == "stats-123"
    drive.update.assert_called_once_with(
        fileId="stats-123",
        body={"name": "FNH 26-27 Stats"},
        fields="id",
    )
