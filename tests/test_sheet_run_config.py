import datetime
from types import SimpleNamespace

import pytest

from roster_scraper import application
from roster_scraper.services import league_sheet_config, sheet_run_config


def test_build_sheet_run_config_converts_valid_config():
    league_config = league_sheet_config.LeagueConfig(
        league_id="12922",
        league_name="FNH 26-27",
        season="just_started",
        start_date_override="2026-10-09",
        last_run="2026-10-08T12:00:00",
    )

    result = sheet_run_config.build_sheet_run_config(league_config, "1")

    assert result.league_config is league_config
    assert result.scrape_config == application.ScrapeConfig(
        league_id="12922",
        season_mode=application.SEASON_MODES_BY_NAME["just_started"],
        output_format="1",
        start_date_override=datetime.date(2026, 10, 9),
    )


def test_build_sheet_run_config_accepts_blank_optional_date():
    league_config = league_sheet_config.LeagueConfig(
        league_id="12922",
        season="preseason",
    )

    result = sheet_run_config.build_sheet_run_config(league_config, "1")

    assert result.scrape_config.start_date_override is None


@pytest.mark.parametrize("league_id", ["", "abc", "12.5", "１２", None, 12922])
def test_build_sheet_run_config_rejects_invalid_league_id(league_id):
    league_config = league_sheet_config.LeagueConfig(
        league_id=league_id,
        season="in_season",
    )

    with pytest.raises(sheet_run_config.SheetConfigError, match="league_id"):
        sheet_run_config.build_sheet_run_config(league_config, "1")


@pytest.mark.parametrize("season", ["", "started", "IN_SEASON", None])
def test_build_sheet_run_config_rejects_unknown_season(season):
    league_config = league_sheet_config.LeagueConfig(
        league_id="12922",
        season=season,
    )

    with pytest.raises(sheet_run_config.SheetConfigError, match="season must be one of"):
        sheet_run_config.build_sheet_run_config(league_config, "1")


@pytest.mark.parametrize("value", ["2026-1-09", "2026-10-9", "2026-13-01", "tomorrow"])
def test_parse_start_date_override_rejects_malformed_date(value):
    with pytest.raises(sheet_run_config.SheetConfigError, match="YYYY-MM-DD"):
        sheet_run_config.parse_start_date_override(value)


def test_build_sheet_run_config_requires_output_format():
    league_config = league_sheet_config.LeagueConfig(
        league_id="12922",
        season="in_season",
    )

    with pytest.raises(sheet_run_config.SheetConfigError, match="output format"):
        sheet_run_config.build_sheet_run_config(league_config, "")


def test_load_sheet_run_config_reads_hidden_config(monkeypatch):
    service = object()
    league_config = league_sheet_config.LeagueConfig(
        league_id="12922",
        season="in_season",
    )
    calls = []
    monkeypatch.setattr(
        sheet_run_config.league_sheet_config,
        "read_league_config",
        lambda service_arg, spreadsheet_id: (
            calls.append((service_arg, spreadsheet_id)) or league_config
        ),
    )

    result = sheet_run_config.load_sheet_run_config(service, "sheet-123", "1")

    assert calls == [(service, "sheet-123")]
    assert result.league_config is league_config


def test_load_sheet_run_config_propagates_sheet_read_error():
    error = RuntimeError("Google Sheets unavailable")
    service = SimpleNamespace(
        values=lambda: SimpleNamespace(
            get=lambda **kwargs: SimpleNamespace(execute=lambda: (_ for _ in ()).throw(error))
        )
    )

    with pytest.raises(RuntimeError, match="Google Sheets unavailable"):
        sheet_run_config.load_sheet_run_config(service, "sheet-123", "1")


@pytest.mark.parametrize("timezone", ["Invalid/Zone", "../../../etc/passwd", "+03:00", "", None])
def test_sheet_config_rejects_invalid_timezone(timezone):
    config = league_sheet_config.LeagueConfig(
        league_id="12922", season="in_season", timezone=timezone
    )

    with pytest.raises(sheet_run_config.SheetConfigError, match="valid IANA name"):
        sheet_run_config.build_sheet_run_config(config, "1")


def test_sheet_timezone_does_not_change_schedule_date_override():
    config = league_sheet_config.LeagueConfig(
        league_id="12922",
        season="in_season",
        timezone="America/New_York",
        start_date_override="2026-10-09",
    )

    result = sheet_run_config.build_sheet_run_config(config, "1")

    assert result.league_config.timezone == "America/New_York"
    assert result.scrape_config.start_date_override == datetime.date(2026, 10, 9)
