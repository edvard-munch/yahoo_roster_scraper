from types import SimpleNamespace

import bs4

from roster_scraper import cli


class StatsSinkSpy:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_prepare_league_returns_noninteractive_discovery_result(monkeypatch):
    soup = bs4.BeautifulSoup("<html></html>", "lxml")
    proxy = {"http": "proxy", "https": "proxy"}
    calls = []
    monkeypatch.setattr(
        cli,
        "parse_full_page",
        lambda link, proxies, current_proxy=None: (soup, proxy),
    )
    monkeypatch.setattr(
        cli,
        "resolve_league_links",
        lambda soup_arg, link, league_id, season_mode, proxies, current_proxy: (
            calls.append((soup_arg, link, league_id, season_mode, proxies, current_proxy))
            or ((["matchup"], ["team"]), proxy)
        ),
    )
    season_mode = cli.SEASON_MODES[cli.SEASON_CHOICES["in_season"]]

    prepared = cli.prepare_league("11249", season_mode, [])

    assert prepared == cli.PreparedLeague(
        soup=soup,
        links=(["matchup"], ["team"]),
        proxies=[],
        current_proxy=proxy,
    )
    assert calls[0][1] == f"{cli.BASE_FANTASY_URL}11249"


def test_prepare_league_returns_none_when_no_team_links(monkeypatch):
    soup = bs4.BeautifulSoup("<html></html>", "lxml")
    monkeypatch.setattr(cli, "parse_full_page", lambda *args, **kwargs: (soup, None))
    monkeypatch.setattr(
        cli,
        "resolve_league_links",
        lambda *args, **kwargs: (([], []), None),
    )

    assert (
        cli.prepare_league(
            "11249",
            cli.SEASON_MODES[cli.SEASON_CHOICES["in_season"]],
            [],
        )
        is None
    )


def test_run_scrape_full_stats_uses_config_and_sink_without_prompting(monkeypatch):
    soup = bs4.BeautifulSoup("<html></html>", "lxml")
    prepared = cli.PreparedLeague(
        soup=soup,
        links=(["matchup"], ["team"]),
        proxies=[],
        current_proxy="initial-proxy",
    )
    config = cli.ScrapeConfig(
        league_id="11249",
        season_mode=cli.SEASON_MODES[cli.SEASON_CHOICES["just_started"]],
        output_format=cli.FORMAT_CHOICES["xlsx"],
        start_date_override=None,
    )
    sink = StatsSinkSpy()
    schedule_calls = []
    process_calls = []
    monkeypatch.setattr(
        "builtins.input",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("runner must not prompt")),
    )
    monkeypatch.setattr(
        cli.core_output,
        "open_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("runner must not open local files")
        ),
    )
    monkeypatch.setattr(
        cli.google_api_auth,
        "sheet_service",
        lambda: (_ for _ in ()).throw(AssertionError("runner must not launch OAuth")),
    )
    monkeypatch.setattr(
        cli,
        "get_matchup_date_range",
        lambda *args, **kwargs: (None, "initial-proxy"),
    )
    monkeypatch.setattr(
        cli.schedule_scraper,
        "get_schedule",
        lambda **kwargs: schedule_calls.append(kwargs) or ({"BOS": {"GL": 2}}, None),
    )
    monkeypatch.setattr(
        cli,
        "build_roster_context",
        lambda stats_sink, context, season_mode: (stats_sink, context, season_mode),
    )
    monkeypatch.setattr(
        cli.roster_workflow,
        "process_links",
        lambda *args, **kwargs: process_calls.append((args, kwargs)) or "final-proxy",
    )

    result = cli.run_scrape(config, prepared, SimpleNamespace(), sink)

    assert result == "final-proxy"
    assert schedule_calls == [{"start_date": None, "end_date": None, "start_date_override": None}]
    assert process_calls[0][0][1] == ["team"]
    assert process_calls[0][0][3] == cli.FORMAT_CHOICES["xlsx"]
    assert process_calls[0][1]["proxy"] == "initial-proxy"
    assert sink.closed is True


def test_run_scrape_non_stats_does_not_require_sink(monkeypatch):
    soup = bs4.BeautifulSoup("<html></html>", "lxml")
    prepared = cli.PreparedLeague(
        soup=soup,
        links=([], ["team"]),
        proxies=[],
    )
    config = cli.ScrapeConfig(
        league_id="11249",
        season_mode=cli.SEASON_MODES[cli.SEASON_CHOICES["preseason"]],
        output_format=cli.FORMAT_CHOICES["txt"],
    )
    process_calls = []
    monkeypatch.setattr(cli, "build_roster_context", lambda *args: "context")
    monkeypatch.setattr(
        cli.roster_workflow,
        "process_links",
        lambda *args, **kwargs: process_calls.append((args, kwargs)) or None,
    )

    assert cli.run_scrape(config, prepared, SimpleNamespace()) is None
    assert process_calls[0][0][0] == "context"
    assert process_calls[0][0][1] == ["team"]
    assert process_calls[0][0][3] == cli.FORMAT_CHOICES["txt"]
    assert process_calls[0][0][4] == cli.RESEARCH_STATS_PAGE
