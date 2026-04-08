import bs4
import datetime

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
        lambda league_id, proxies, proxy=None: (["/standing/1", "/standing/2"], proxy),
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
    inputs = iter(["19715", ""])
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
    monkeypatch.setattr(
        cli.schedule_scraper,
        "get_schedule",
        lambda proxies, proxy=None, schedule_url=None, start_date=None, end_date=None: (
            {"BOS": {"GL": 3}},
            proxy,
        ),
    )
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


def test_main_reuses_working_proxy_across_xlsx_steps(monkeypatch):
    validate_results = iter(["Y", cli.FORMAT_CHOICES["xlsx"]])
    inputs = iter(["19715", ""])
    parse_calls = []
    schedule_calls = []
    process_calls = []

    stable_proxy = {"http": "9.9.9.9:80", "https": "9.9.9.9:80"}

    workbook = type(
        "WorkbookSpy",
        (),
        {
            "__init__": lambda self, filename: setattr(self, "filename", filename),
            "add_worksheet": lambda self, name: type("WorksheetSpy", (), {"name": name})(),
            "close": lambda self: None,
        },
    )

    monkeypatch.setattr(cli, "validate_input", lambda *args, **kwargs: next(validate_results))
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: next(inputs))
    monkeypatch.setattr(cli.proxies_scraper, "scrape_proxies", lambda: [stable_proxy])
    monkeypatch.setattr(
        cli,
        "parse_full_page",
        lambda link, proxies, proxy=None, params=None: (
            parse_calls.append({"link": link, "proxy": proxy})
            or bs4.BeautifulSoup("<html></html>", "lxml"),
            stable_proxy,
        ),
    )
    monkeypatch.setattr(
        cli,
        "get_links",
        lambda *args, **kwargs: (["https://example.com/matchup/1"], ["/team/1"]),
    )
    monkeypatch.setattr(
        cli.schedule_scraper,
        "get_schedule",
        lambda proxies, proxy=None, schedule_url=None, start_date=None, end_date=None: (
            schedule_calls.append({"proxy": proxy, "schedule_url": schedule_url})
            or ({"BOS": {"GL": 3}}, proxy)
        ),
    )
    monkeypatch.setattr(cli.xlsxwriter, "Workbook", workbook)
    monkeypatch.setattr(cli, "build_roster_context", lambda *args, **kwargs: "context")
    monkeypatch.setattr(
        cli.roster_workflow,
        "process_links",
        lambda *args, **kwargs: process_calls.append(kwargs) or kwargs["proxy"],
    )
    monkeypatch.setattr(cli.core_output, "get_filename", lambda: "reports/test.xlsx")
    monkeypatch.setattr(cli.core_output, "open_file", lambda filename: None)

    cli.main()

    assert parse_calls[0]["proxy"] is None
    assert schedule_calls[0]["proxy"] == stable_proxy
    assert schedule_calls[0]["schedule_url"] is None
    assert process_calls[0]["proxy"] == stable_proxy


def test_main_passes_custom_schedule_url_override_to_schedule_scraper(monkeypatch):
    validate_results = iter(["n", cli.FORMAT_CHOICES["xlsx"]])
    inputs = iter(["19715", "https://example.com/custom-schedule"])
    schedule_calls = []

    workbook = type(
        "WorkbookSpy",
        (),
        {
            "__init__": lambda self, filename: setattr(self, "filename", filename),
            "add_worksheet": lambda self, name: type("WorksheetSpy", (), {"name": name})(),
            "close": lambda self: None,
        },
    )

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
    monkeypatch.setattr(
        cli.schedule_scraper,
        "get_schedule",
        lambda proxies, proxy=None, schedule_url=None, start_date=None, end_date=None: (
            schedule_calls.append(
                {
                    "proxy": proxy,
                    "schedule_url": schedule_url,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )
            or ({"BOS": {"GL": 3}}, proxy)
        ),
    )
    monkeypatch.setattr(cli.xlsxwriter, "Workbook", workbook)
    monkeypatch.setattr(cli, "build_roster_context", lambda *args, **kwargs: "context")
    monkeypatch.setattr(cli.roster_workflow, "process_links", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli.core_output, "get_filename", lambda: "reports/test.xlsx")
    monkeypatch.setattr(cli.core_output, "open_file", lambda filename: None)

    cli.main()

    assert schedule_calls[0]["schedule_url"] == "https://example.com/custom-schedule"
    assert schedule_calls[0]["start_date"] is None
    assert schedule_calls[0]["end_date"] is None


def test_main_uses_matchup_date_range_for_longer_than_week_xlsx(monkeypatch):
    validate_results = iter(["n", cli.FORMAT_CHOICES["xlsx"]])
    inputs = iter(["19715", ""])
    schedule_calls = []

    workbook = type(
        "WorkbookSpy",
        (),
        {
            "__init__": lambda self, filename: setattr(self, "filename", filename),
            "add_worksheet": lambda self, name: type("WorksheetSpy", (), {"name": name})(),
            "close": lambda self: None,
        },
    )

    monkeypatch.setattr(cli, "validate_input", lambda *args, **kwargs: next(validate_results))
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: next(inputs))

    real_date = datetime.date

    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return cls(2026, 4, 1)

    monkeypatch.setattr(cli.datetime, "date", FakeDate)
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
    monkeypatch.setattr(
        cli,
        "get_matchup_date_range",
        lambda *args, **kwargs: ((datetime.date(2026, 3, 25), datetime.date(2026, 4, 4)), None),
    )
    monkeypatch.setattr(
        cli.schedule_scraper,
        "get_schedule",
        lambda proxies, proxy=None, schedule_url=None, start_date=None, end_date=None: (
            schedule_calls.append(
                {
                    "schedule_url": schedule_url,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )
            or ({"BOS": {"GL": 3}}, proxy)
        ),
    )
    monkeypatch.setattr(cli.xlsxwriter, "Workbook", workbook)
    monkeypatch.setattr(cli, "build_roster_context", lambda *args, **kwargs: "context")
    monkeypatch.setattr(cli.roster_workflow, "process_links", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli.core_output, "get_filename", lambda: "reports/test.xlsx")
    monkeypatch.setattr(cli.core_output, "open_file", lambda filename: None)

    cli.main()

    assert schedule_calls[0]["schedule_url"] is None
    assert schedule_calls[0]["start_date"] == real_date(2026, 4, 1)
    assert schedule_calls[0]["end_date"] == datetime.date(2026, 4, 4)


def test_main_falls_back_to_weekly_schedule_when_matchup_range_not_detected(monkeypatch):
    validate_results = iter(["n", cli.FORMAT_CHOICES["xlsx"]])
    inputs = iter(["19715", ""])
    schedule_calls = []

    workbook = type(
        "WorkbookSpy",
        (),
        {
            "__init__": lambda self, filename: setattr(self, "filename", filename),
            "add_worksheet": lambda self, name: type("WorksheetSpy", (), {"name": name})(),
            "close": lambda self: None,
        },
    )

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
    monkeypatch.setattr(cli, "get_matchup_date_range", lambda *args, **kwargs: (None, None))
    monkeypatch.setattr(
        cli.schedule_scraper,
        "get_schedule",
        lambda proxies, proxy=None, schedule_url=None, start_date=None, end_date=None: (
            schedule_calls.append(
                {
                    "schedule_url": schedule_url,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )
            or ({"BOS": {"GL": 3}}, proxy)
        ),
    )
    monkeypatch.setattr(cli.xlsxwriter, "Workbook", workbook)
    monkeypatch.setattr(cli, "build_roster_context", lambda *args, **kwargs: "context")
    monkeypatch.setattr(cli.roster_workflow, "process_links", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli.core_output, "get_filename", lambda: "reports/test.xlsx")
    monkeypatch.setattr(cli.core_output, "open_file", lambda filename: None)

    cli.main()

    assert schedule_calls[0]["schedule_url"] is None
    assert schedule_calls[0]["start_date"] is None
    assert schedule_calls[0]["end_date"] is None
