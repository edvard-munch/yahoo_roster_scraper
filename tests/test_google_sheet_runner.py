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


def capture_status_writes(monkeypatch):
    writes = []
    monkeypatch.setattr(
        google_sheet_runner.league_sheet_config,
        "build_last_run_timestamp",
        lambda: "2026-10-08T12:00:00",
    )
    monkeypatch.setattr(
        google_sheet_runner.league_sheet_config,
        "write_league_config",
        lambda service, spreadsheet_id, config: writes.append(
            {
                "service": service,
                "spreadsheet_id": spreadsheet_id,
                "status": config.run_status,
                "started_at": config.run_started_at,
                "last_error": config.last_error,
                "last_run": config.last_run,
            }
        ),
    )
    return writes


def test_runner_connects_sheet_config_preparation_sink_and_application(monkeypatch):
    service = object()
    dependencies = SimpleNamespace(xlsx_format="1")
    matchups_context = object()
    sheet_config = make_sheet_config()
    prepared = object()
    calls = []
    status_writes = capture_status_writes(monkeypatch)
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

    def run_scrape(config, prepared_arg, context, dependencies_arg, sink):
        calls.append(("run", config, prepared_arg, context, dependencies_arg, sink))
        sink.config.last_run = "2026-10-08T12:01:00"
        return "final-proxy"

    monkeypatch.setattr(google_sheet_runner.application, "run_scrape", run_scrape)

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
    assert status_writes == [
        {
            "service": service,
            "spreadsheet_id": "sheet-123",
            "status": "running",
            "started_at": "2026-10-08T12:00:00",
            "last_error": None,
            "last_run": None,
        },
        {
            "service": service,
            "spreadsheet_id": "sheet-123",
            "status": "complete",
            "started_at": "2026-10-08T12:00:00",
            "last_error": None,
            "last_run": "2026-10-08T12:01:00",
        },
    ]


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
    status_writes = capture_status_writes(monkeypatch)
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
    assert [write["status"] for write in status_writes] == ["running", "failed"]
    assert status_writes[-1]["last_error"].startswith("LeaguePreparationError:")


def test_runner_does_not_update_last_run_when_application_fails(monkeypatch):
    status_writes = capture_status_writes(monkeypatch)
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
    assert [write["status"] for write in status_writes] == ["running", "failed"]
    assert status_writes[-1]["last_error"] == "RuntimeError: scrape failed"


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


def test_failed_status_write_does_not_replace_original_scrape_error(monkeypatch):
    sheet_config = make_sheet_config()
    original_error = RuntimeError("original scrape failure")
    write_calls = []
    monkeypatch.setattr(
        google_sheet_runner.sheet_run_config,
        "load_sheet_run_config",
        lambda *args, **kwargs: sheet_config,
    )
    monkeypatch.setattr(
        google_sheet_runner.league_sheet_config,
        "build_last_run_timestamp",
        lambda: "2026-10-08T12:00:00",
    )

    def write_config(service, spreadsheet_id, config):
        write_calls.append(config.run_status)
        if config.run_status == "failed":
            raise RuntimeError("status write failure")

    monkeypatch.setattr(
        google_sheet_runner.league_sheet_config,
        "write_league_config",
        write_config,
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
        lambda *args, **kwargs: (_ for _ in ()).throw(original_error),
    )

    with pytest.raises(RuntimeError, match="original scrape failure") as caught:
        google_sheet_runner.run_google_sheet_scrape(
            object(),
            "sheet-123",
            SimpleNamespace(xlsx_format="1"),
            object(),
        )

    assert caught.value is original_error
    assert write_calls == ["running", "failed"]
    assert any("status write failure" in note for note in caught.value.__notes__)


def test_format_run_error_is_bounded():
    error = RuntimeError("x" * (google_sheet_runner.MAX_ERROR_MESSAGE_LENGTH + 100))

    message = google_sheet_runner.format_run_error(error)

    assert message.startswith("RuntimeError: ")
    assert len(message) == google_sheet_runner.MAX_ERROR_MESSAGE_LENGTH
