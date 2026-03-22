import bs4

from roster_scraper import cli


def test_main_retries_invalid_proxy_and_league_then_runs_txt(monkeypatch):
    validate_results = iter([None, "n", None, cli.FORMAT_CHOICES["txt"]])
    inputs = iter(["bad-league", "good-league"])
    links_results = iter(
        [
            None,
            (["https://example.com/matchup/1"], ["/team/1"]),
        ]
    )
    process_calls = []
    opened_files = []

    monkeypatch.setattr(cli, "validate_input", lambda *args, **kwargs: next(validate_results))
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: next(inputs))
    monkeypatch.setattr(
        cli,
        "parse_full_page",
        lambda *args, **kwargs: (bs4.BeautifulSoup("<html></html>", "lxml"), None),
    )
    monkeypatch.setattr(cli, "get_links", lambda *args, **kwargs: next(links_results))
    monkeypatch.setattr(cli, "build_roster_context", lambda *args, **kwargs: "context")
    monkeypatch.setattr(
        cli.roster_workflow,
        "process_links",
        lambda *args, **kwargs: process_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        cli.core_output, "open_file", lambda filename: opened_files.append(filename)
    )

    cli.main()

    assert len(process_calls) == 1
    args, _ = process_calls[0]
    assert args[0] == "context"
    assert args[1] == ["/team/1"]
    assert args[2] == []
    assert args[3] == cli.FORMAT_CHOICES["txt"]
    assert args[4] == cli.RESEARCH_STATS_PAGE
    assert opened_files == [cli.TXT_FILENAME]


def test_main_uses_standings_links_for_json_when_playoffs_header_present(monkeypatch):
    validate_results = iter(["n", cli.FORMAT_CHOICES["json"]])
    inputs = iter(["19715"])
    process_calls = []
    opened_files = []

    playoffs_soup = bs4.BeautifulSoup(f"<html><body>{cli.PLAYOFFS_HEADER}</body></html>", "lxml")

    monkeypatch.setattr(cli, "validate_input", lambda *args, **kwargs: next(validate_results))
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: next(inputs))
    monkeypatch.setattr(cli, "parse_full_page", lambda *args, **kwargs: (playoffs_soup, None))
    monkeypatch.setattr(
        cli,
        "get_links",
        lambda *args, **kwargs: (["https://example.com/matchup/1"], ["/team/1"]),
    )
    monkeypatch.setattr(
        cli,
        "get_links_from_standings",
        lambda league_id, proxies: ["/standing/1", "/standing/2"],
    )
    monkeypatch.setattr(cli, "build_roster_context", lambda *args, **kwargs: "context")
    monkeypatch.setattr(
        cli.roster_workflow,
        "process_links",
        lambda *args, **kwargs: process_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        cli.core_output, "open_file", lambda filename: opened_files.append(filename)
    )

    cli.main()

    assert len(process_calls) == 1
    args, _ = process_calls[0]
    assert args[1] == ["/standing/1", "/standing/2"]
    assert args[3] == cli.FORMAT_CHOICES["json"]
    assert opened_files == [cli.POSITIONS_FILENAME]


def test_main_runs_google_mode_without_opening_local_file(monkeypatch):
    validate_results = iter(["n", cli.FORMAT_CHOICES["google_sheets"]])
    inputs = iter(["19715"])
    process_calls = []
    opened_files = []

    monkeypatch.setattr(cli, "validate_input", lambda *args, **kwargs: next(validate_results))
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: next(inputs))
    monkeypatch.setattr(
        cli,
        "parse_full_page",
        lambda *args, **kwargs: (bs4.BeautifulSoup("<html></html>", "lxml"), None),
    )
    monkeypatch.setattr(
        cli,
        "get_links",
        lambda *args, **kwargs: (["https://example.com/matchup/1"], ["/team/1"]),
    )
    monkeypatch.setattr(cli, "build_roster_context", lambda *args, **kwargs: "context")
    monkeypatch.setattr(
        cli.roster_workflow,
        "process_links",
        lambda *args, **kwargs: process_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        cli.core_output, "open_file", lambda filename: opened_files.append(filename)
    )

    cli.main()

    assert len(process_calls) == 1
    args, _ = process_calls[0]
    assert args[3] == cli.FORMAT_CHOICES["google_sheets"]
    assert opened_files == []


def test_main_xlsx_uses_season_start_avg_stats_when_enabled(monkeypatch):
    validate_results = iter(["n", cli.FORMAT_CHOICES["xlsx"]])
    inputs = iter(["19715"])
    process_calls = []
    opened_files = []

    workbook = type(
        "WorkbookSpy",
        (),
        {
            "__init__": lambda self, filename: setattr(self, "filename", filename),
            "add_worksheet": lambda self, name: type("WorksheetSpy", (), {"name": name})(),
            "close": lambda self: None,
        },
    )

    monkeypatch.setattr(cli, "SEASON_JUST_STARTED", True)
    monkeypatch.setattr(cli, "AVG_STATS_PAGE", {"stat1": "AS", "stat2": "AS_2025"})
    monkeypatch.setattr(cli, "validate_input", lambda *args, **kwargs: next(validate_results))
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: next(inputs))
    monkeypatch.setattr(
        cli,
        "parse_full_page",
        lambda *args, **kwargs: (bs4.BeautifulSoup("<html></html>", "lxml"), None),
    )
    monkeypatch.setattr(
        cli,
        "get_links",
        lambda *args, **kwargs: (["https://example.com/matchup/1"], ["/team/1"]),
    )
    monkeypatch.setattr(cli.schedule_scraper, "get_schedule", lambda proxies: {"BOS": {"GL": 3}})
    monkeypatch.setattr(cli.xlsxwriter, "Workbook", workbook)
    monkeypatch.setattr(cli, "build_roster_context", lambda *args, **kwargs: "context")
    monkeypatch.setattr(
        cli.roster_workflow,
        "process_links",
        lambda *args, **kwargs: process_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(cli.core_output, "get_filename", lambda: "reports/test.xlsx")
    monkeypatch.setattr(
        cli.core_output, "open_file", lambda filename: opened_files.append(filename)
    )

    cli.main()

    assert len(process_calls) == 1
    args, _ = process_calls[0]
    assert args[3] == cli.FORMAT_CHOICES["xlsx"]
    assert args[4] == {"stat1": "AS", "stat2": "AS_2025"}
    assert opened_files == ["reports/test.xlsx"]
