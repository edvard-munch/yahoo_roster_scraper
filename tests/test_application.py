from types import SimpleNamespace

import bs4

from roster_scraper import application


class StatsSinkSpy:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def build_dependencies(**overrides):
    defaults = {
        "base_fantasy_url": "https://example.com/league/",
        "xlsx_format": "1",
        "matchup_range_days_threshold": 7,
        "playoffs_header": "Championship Bracket",
        "research_stats_page": {"stat1": "R"},
        "parse_full_page": lambda *args, **kwargs: (
            bs4.BeautifulSoup("<html></html>", "lxml"),
            None,
        ),
        "resolve_league_links": lambda *args, **kwargs: ((["matchup"], ["team"]), None),
        "get_matchup_date_range": lambda *args, **kwargs: (None, None),
        "get_links_from_standings": lambda *args, **kwargs: (["standing-team"], None),
        "get_schedule": lambda **kwargs: ({}, None),
        "build_roster_context": lambda *args: "context",
        "build_avg_stats_page": lambda just_started: {"just_started": just_started},
        "process_links": lambda *args, **kwargs: None,
        "today": lambda: application.datetime.date(2026, 10, 1),
    }
    defaults.update(overrides)
    return application.ScrapeDependencies(**defaults)


def test_prepare_league_returns_noninteractive_discovery_result():
    soup = bs4.BeautifulSoup("<html></html>", "lxml")
    proxy = {"http": "proxy", "https": "proxy"}
    calls = []
    dependencies = build_dependencies(
        parse_full_page=lambda link, proxies, current_proxy=None: (soup, proxy),
        resolve_league_links=lambda soup_arg, link, league_id, season_mode, proxies, current_proxy: (
            calls.append((soup_arg, link, league_id, season_mode, proxies, current_proxy))
            or ((["matchup"], ["team"]), proxy)
        ),
    )
    season_mode = application.SeasonMode(in_progress=True, just_started=False)

    prepared = application.prepare_league("11249", season_mode, [], dependencies)

    assert prepared == application.PreparedLeague(
        soup=soup,
        links=(["matchup"], ["team"]),
        proxies=[],
        current_proxy=proxy,
    )
    assert calls[0][1] == "https://example.com/league/11249"


def test_prepare_league_returns_none_when_no_team_links():
    dependencies = build_dependencies(resolve_league_links=lambda *args, **kwargs: (([], []), None))

    assert (
        application.prepare_league(
            "11249",
            application.SeasonMode(in_progress=True, just_started=False),
            [],
            dependencies,
        )
        is None
    )


def test_run_scrape_full_stats_uses_config_and_sink():
    prepared = application.PreparedLeague(
        soup=bs4.BeautifulSoup("<html></html>", "lxml"),
        links=(["matchup"], ["team"]),
        proxies=[],
        current_proxy="initial-proxy",
    )
    config = application.ScrapeConfig(
        league_id="11249",
        season_mode=application.SeasonMode(in_progress=True, just_started=True),
        output_format="1",
    )
    sink = StatsSinkSpy()
    schedule_calls = []
    process_calls = []
    dependencies = build_dependencies(
        get_matchup_date_range=lambda *args, **kwargs: (None, "initial-proxy"),
        get_schedule=lambda **kwargs: schedule_calls.append(kwargs) or ({"BOS": {"GL": 2}}, None),
        build_roster_context=lambda stats_sink, context, season_mode: (
            stats_sink,
            context,
            season_mode,
        ),
        process_links=lambda *args, **kwargs: process_calls.append((args, kwargs)) or "final-proxy",
    )

    result = application.run_scrape(
        config,
        prepared,
        SimpleNamespace(),
        dependencies,
        sink,
    )

    assert result == "final-proxy"
    assert schedule_calls == [{"start_date": None, "end_date": None, "start_date_override": None}]
    assert process_calls[0][0][1] == ["team"]
    assert process_calls[0][0][3] == "1"
    assert process_calls[0][1]["proxy"] == "initial-proxy"
    assert sink.closed is True


def test_run_scrape_non_stats_does_not_require_sink():
    prepared = application.PreparedLeague(
        soup=bs4.BeautifulSoup("<html></html>", "lxml"),
        links=([], ["team"]),
        proxies=[],
    )
    config = application.ScrapeConfig(
        league_id="11249",
        season_mode=application.SeasonMode(in_progress=False, just_started=False),
        output_format="2",
    )
    process_calls = []
    dependencies = build_dependencies(
        process_links=lambda *args, **kwargs: process_calls.append((args, kwargs)) or None
    )

    assert application.run_scrape(config, prepared, SimpleNamespace(), dependencies) is None
    assert process_calls[0][0][0] == "context"
    assert process_calls[0][0][1] == ["team"]
    assert process_calls[0][0][3] == "2"
    assert process_calls[0][0][4] == {"stat1": "R"}
