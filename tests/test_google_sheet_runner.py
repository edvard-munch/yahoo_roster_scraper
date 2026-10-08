from types import SimpleNamespace

import pytest

from roster_scraper import application
from roster_scraper.services import google_sheet_runner, league_sheet_config, sheet_run_config


class SinkSpy:
    def __init__(self, service, spreadsheet_id, config):
        self.service = service
        self.spreadsheet_id = spreadsheet_id
        self.config = config


def make_sheet_config():
    league_config = league_sheet_config.LeagueConfig(
        league_id="12922",
        league_name="FNH 26-27",
        season="in_season",
    )
    return sheet_run_config.SheetRunConfig(
        scrape_config=application.ScrapeConfig(
            league_id="12922",
            season_mode=application.SEASON_MODES_BY_NAME["in_season"],
            output_format="1",
        ),
        league_config=league_config,
    )


def test_runner_connects_sheet_config_preparation_sink_and_application(monkeypatch):
    service = object()
    dependencies = SimpleNamespace(xlsx_format="1")
    matchups_context = object()
    sheet_config = make_sheet_config()
    prepared = object()
    calls = []
    monkeypatch.setattr(
        google_sheet_runner.sheet_run_config,
        "load_sheet_run_config",
        lambda service_arg, spreadsheet_id, output_format: (
            calls.append(("load", service_arg, spreadsheet_id, output_format)) or sheet_config
        ),
    )
    monkeypatch.setattr(
        google_sheet_runner.application,
        "prepare_league",
        lambda league_id, season_mode, proxies, dependencies_arg, current_proxy=None: (
            calls.append(
                (
                    "prepare",
                    league_id,
                    season_mode,
                    proxies,
                    dependencies_arg,
                    current_proxy,
                )
            )
            or prepared
        ),
    )
    monkeypatch.setattr(google_sheet_runner.stats_sinks, "GoogleSheetsStatsSink", SinkSpy)
    monkeypatch.setattr(
        google_sheet_runner.application,
        "run_scrape",
        lambda config, prepared_arg, context, dependencies_arg, sink: (
            calls.append(("run", config, prepared_arg, context, dependencies_arg, sink))
            or "final-proxy"
        ),
    )

    result = google_sheet_runner.run_google_sheet_scrape(
        service,
        "sheet-123",
        dependencies,
        matchups_context,
        proxies=["proxy"],
        current_proxy="current-proxy",
    )

    assert result == "final-proxy"
    assert calls[0] == ("load", service, "sheet-123", "1")
    assert calls[1] == (
        "prepare",
        "12922",
        application.SEASON_MODES_BY_NAME["in_season"],
        ["proxy"],
        dependencies,
        "current-proxy",
    )
    _, config, prepared_arg, context, dependencies_arg, sink = calls[2]
    assert config is sheet_config.scrape_config
    assert prepared_arg is prepared
    assert context is matchups_context
    assert dependencies_arg is dependencies
    assert sink.service is service
    assert sink.spreadsheet_id == "sheet-123"
    assert sink.config is sheet_config.league_config


def test_invalid_sheet_config_stops_before_league_preparation(monkeypatch):
    error = sheet_run_config.SheetConfigError("invalid season")
    prepare_calls = []
    monkeypatch.setattr(
        google_sheet_runner.sheet_run_config,
        "load_sheet_run_config",
        lambda *args, **kwargs: (_ for _ in ()).throw(error),
    )
    monkeypatch.setattr(
        google_sheet_runner.application,
        "prepare_league",
        lambda *args, **kwargs: prepare_calls.append(args),
    )

    with pytest.raises(sheet_run_config.SheetConfigError, match="invalid season"):
        google_sheet_runner.run_google_sheet_scrape(
            object(),
            "sheet-123",
            SimpleNamespace(xlsx_format="1"),
            object(),
        )

    assert prepare_calls == []


def test_unavailable_league_stops_before_sink_creation(monkeypatch):
    monkeypatch.setattr(
        google_sheet_runner.sheet_run_config,
        "load_sheet_run_config",
        lambda *args, **kwargs: make_sheet_config(),
    )
    monkeypatch.setattr(
        google_sheet_runner.application,
        "prepare_league",
        lambda *args, **kwargs: None,
    )
    sink_calls = []
    monkeypatch.setattr(
        google_sheet_runner.stats_sinks,
        "GoogleSheetsStatsSink",
        lambda *args: sink_calls.append(args),
    )

    with pytest.raises(google_sheet_runner.LeaguePreparationError, match="12922"):
        google_sheet_runner.run_google_sheet_scrape(
            object(),
            "sheet-123",
            SimpleNamespace(xlsx_format="1"),
            object(),
        )

    assert sink_calls == []


def test_runner_does_not_update_last_run_when_application_fails(monkeypatch):
    sheet_config = make_sheet_config()
    error = RuntimeError("scrape failed")
    monkeypatch.setattr(
        google_sheet_runner.sheet_run_config,
        "load_sheet_run_config",
        lambda *args, **kwargs: sheet_config,
    )
    monkeypatch.setattr(
        google_sheet_runner.application,
        "prepare_league",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(google_sheet_runner.stats_sinks, "GoogleSheetsStatsSink", SinkSpy)
    monkeypatch.setattr(
        google_sheet_runner.application,
        "run_scrape",
        lambda *args, **kwargs: (_ for _ in ()).throw(error),
    )

    with pytest.raises(RuntimeError, match="scrape failed"):
        google_sheet_runner.run_google_sheet_scrape(
            object(),
            "sheet-123",
            SimpleNamespace(xlsx_format="1"),
            object(),
        )

    assert sheet_config.league_config.last_run is None


def test_runner_requires_spreadsheet_id(monkeypatch):
    load_calls = []
    monkeypatch.setattr(
        google_sheet_runner.sheet_run_config,
        "load_sheet_run_config",
        lambda *args, **kwargs: load_calls.append(args),
    )

    with pytest.raises(ValueError, match="Spreadsheet ID"):
        google_sheet_runner.run_google_sheet_scrape(
            object(),
            "",
            SimpleNamespace(xlsx_format="1"),
            object(),
        )

    assert load_calls == []
