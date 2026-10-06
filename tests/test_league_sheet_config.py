import datetime
from types import SimpleNamespace

from roster_scraper.services import league_sheet_config


class ValuesSpy:
    def __init__(self, existing_values=None):
        self.existing_values = existing_values or []
        self.get_calls = []
        self.update_calls = []

    def get(self, spreadsheetId, range):
        self.get_calls.append({"spreadsheetId": spreadsheetId, "range": range})
        return SimpleNamespace(execute=lambda: {"values": self.existing_values})

    def update(self, spreadsheetId, range, valueInputOption, body):
        self.update_calls.append(
            {
                "spreadsheetId": spreadsheetId,
                "range": range,
                "valueInputOption": valueInputOption,
                "body": body,
            }
        )
        return SimpleNamespace(execute=lambda: {})


class ServiceSpy:
    def __init__(self, existing_values=None):
        self._values = ValuesSpy(existing_values)

    def values(self):
        return self._values


def test_config_round_trip_through_rows():
    config = league_sheet_config.LeagueConfig(
        league_id="12922",
        season="preseason",
        start_date_override="2026-10-02",
        last_run="2026-10-02T17:25:00",
    )

    rows = league_sheet_config.config_to_rows(config)

    assert league_sheet_config.config_from_rows(rows) == config


def test_config_from_rows_ignores_blank_and_unknown_keys():
    rows = [
        ["league_id", "12922"],
        ["", "ignored"],
        [],
        ["season", "in_season"],
        ["future_key", "future_value"],
    ]

    config = league_sheet_config.config_from_rows(rows)

    assert config.league_id == "12922"
    assert config.season == "in_season"
    assert config.start_date_override is None
    assert config.last_run is None
    assert config.extras == {"future_key": "future_value"}


def test_read_league_config_uses_config_sheet_range():
    service = ServiceSpy([["league_id", "12922"], ["season", "preseason"]])

    config = league_sheet_config.read_league_config(service, "sheet-123")

    assert service._values.get_calls == [
        {"spreadsheetId": "sheet-123", "range": league_sheet_config.CONFIG_SHEET_TITLE}
    ]
    assert config.league_id == "12922"
    assert config.season == "preseason"


def test_read_league_config_returns_empty_config_when_sheet_missing():
    service = ServiceSpy(existing_values=[])

    config = league_sheet_config.read_league_config(service, "sheet-123")

    assert config == league_sheet_config.LeagueConfig()


def test_write_league_config_writes_rows_to_config_sheet():
    service = ServiceSpy()
    config = league_sheet_config.LeagueConfig(
        league_id="12922",
        season="preseason",
        start_date_override="2026-10-02",
        last_run="2026-10-02T17:25:00",
    )

    league_sheet_config.write_league_config(service, "sheet-123", config)

    assert len(service._values.update_calls) == 1
    call = service._values.update_calls[0]
    assert call["spreadsheetId"] == "sheet-123"
    assert call["range"] == league_sheet_config.CONFIG_SHEET_TITLE
    assert call["valueInputOption"] == "RAW"
    assert call["body"]["values"] == league_sheet_config.config_to_rows(config)


def test_build_last_run_timestamp_formats_datetime():
    now = datetime.datetime(2026, 10, 2, 17, 25, 0)

    assert league_sheet_config.build_last_run_timestamp(now) == "2026-10-02T17:25:00"
