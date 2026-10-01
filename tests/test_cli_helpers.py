from types import SimpleNamespace

import bs4

from roster_scraper import cli


def test_get_team_name_prefers_name_span(monkeypatch):
    monkeypatch.setattr(
        cli,
        "scrape_from_page",
        lambda *args, **kwargs: [SimpleNamespace(text="  Preferred Team Name  ")],
    )

    name = cli.get_team_name(bs4.BeautifulSoup("<html></html>", "lxml"))

    assert name == "Preferred Team Name"


def test_get_team_name_uses_title_when_span_missing():
    soup = bs4.BeautifulSoup(
        "<html><head><title>Title Team | Yahoo Fantasy Sports</title></head></html>",
        "lxml",
    )

    name = cli.get_team_name(soup)

    assert name == "Title Team"


def test_get_team_name_extracts_team_part_from_hyphenated_title():
    soup = bs4.BeautifulSoup(
        "<html><head><title>FNH 25-26 - Brewers team | Fantasy Hockey | Yahoo! Sports</title></head></html>",
        "lxml",
    )

    name = cli.get_team_name(soup)

    assert name == "Brewers team"


def test_get_team_name_uses_fallback_span_and_removes_private_glyphs():
    soup = bs4.BeautifulSoup(
        "<html><body><span class='F-reset Nowrap'>Brewers team \ue002</span></body></html>",
        "lxml",
    )

    name = cli.get_team_name(soup)

    assert name == "Brewers team"


def test_get_team_name_uses_truncated_fallback_when_needed():
    fallback_name = "A" * 40
    soup = bs4.BeautifulSoup("<html><head></head><body></body></html>", "lxml")

    name = cli.get_team_name(soup, fallback_name=fallback_name)

    assert name == "A" * 30


def test_parse_full_page_without_proxies_uses_direct_response(monkeypatch):
    calls = {}

    def fake_get_response(link, params):
        calls["link"] = link
        calls["params"] = params
        return SimpleNamespace(text="<html><body><p>ok</p></body></html>")

    monkeypatch.setattr(cli.proxies_scraper, "get_response", fake_get_response)

    soup, proxy = cli.parse_full_page("https://example.com", proxies=[])

    assert calls == {"link": "https://example.com", "params": {}}
    assert soup.find("p").get_text(strip=True) == "ok"
    assert proxy is None


def test_parse_full_page_with_proxies_uses_retry_helper(monkeypatch):
    calls = {}
    expected_proxy = {"http": "2.2.2.2:80", "https": "2.2.2.2:80"}

    def fake_get_response_with_retries(link, params, proxies, failure_target, proxy):
        calls["link"] = link
        calls["params"] = params
        calls["proxies"] = proxies
        calls["failure_target"] = failure_target
        calls["proxy"] = proxy
        return SimpleNamespace(text="<html><body><p>proxy</p></body></html>"), expected_proxy

    monkeypatch.setattr(
        cli.proxies_scraper,
        "get_response_with_retries",
        fake_get_response_with_retries,
    )

    proxies_list = [{"http": "1.1.1.1:80", "https": "1.1.1.1:80"}]
    initial_proxy = {"http": "3.3.3.3:80", "https": "3.3.3.3:80"}

    soup, proxy = cli.parse_full_page(
        "https://example.com",
        proxies=proxies_list,
        proxy=initial_proxy,
        params={"stat1": "AS"},
    )

    assert calls["link"] == "https://example.com"
    assert calls["params"] == {"stat1": "AS"}
    assert calls["proxies"] == proxies_list
    assert calls["failure_target"] == cli.proxies_scraper.PROXY_FAILURE_TARGET_PAGE
    assert calls["proxy"] == initial_proxy
    assert soup.find("p").get_text(strip=True) == "proxy"
    assert proxy == expected_proxy


def test_get_links_returns_matchup_and_team_links():
    league_link = "https://hockey.fantasysports.yahoo.com/hockey/19715"
    html = """
    <html>
      <body>
        <li class="Linkable Listitem No-p" data-target="/hockey/19715/matchup/123">
          <div class="Fz-sm Phone-fz-xs Ell"><a href="/team/1">Team 1</a></div>
          <div class="Fz-sm Phone-fz-xs Ell"><a href="/team/2">Team 2</a></div>
        </li>
      </body>
    </html>
    """
    soup = bs4.BeautifulSoup(html, "lxml")

    links = cli.get_links(soup, league_link)

    assert links[0] == [f"{league_link}/123"]
    assert links[1] == ["/team/1", "/team/2"]


def test_get_links_returns_empty_lists_when_no_matchups_found():
    soup = bs4.BeautifulSoup("<html><body><p>empty</p></body></html>", "lxml")

    links = cli.get_links(soup, "https://hockey.fantasysports.yahoo.com/hockey/19715")

    assert links == ([], [])


def test_extract_team_id_handles_league_and_year_links():
    assert cli.extract_team_id("https://hockey.fantasysports.yahoo.com/hockey/12922/4") == "4"
    assert cli.extract_team_id("https://hockey.fantasysports.yahoo.com/2025/hockey/19715/4") == "4"
    assert cli.extract_team_id("https://example.com/not-a-team") is None


def test_merge_team_links_dedupes_by_name_and_falls_back_to_team_id():
    league_link = "https://hockey.fantasysports.yahoo.com/hockey/12922/4"
    same_name_link = "https://hockey.fantasysports.yahoo.com/2025/hockey/19715/8"
    extra_team_link = "https://hockey.fantasysports.yahoo.com/2025/hockey/19715/12"

    merged = cli.merge_team_links(
        [(league_link, "Dekes and Geek(ie)s")],
        [(same_name_link, "Dekes and Geek(ie)s"), (extra_team_link, "New Team")],
    )

    assert merged == [league_link, extra_team_link]


def test_merge_team_links_dedupes_unnamed_links_by_team_id():
    league_link = "https://hockey.fantasysports.yahoo.com/hockey/12922/4"
    same_id_link = "https://hockey.fantasysports.yahoo.com/2025/hockey/19715/4"

    merged = cli.merge_team_links([(league_link, None)], [(same_id_link, None)])

    assert merged == [league_link]


def test_resolve_league_links_merges_league_and_standings_in_preseason(monkeypatch, capsys):
    season_mode = cli.SEASON_MODES[cli.SEASON_CHOICES["preseason"]]
    league_link = "https://hockey.fantasysports.yahoo.com/hockey/12922"
    monkeypatch.setattr(cli, "get_links", lambda *args, **kwargs: ([], []))
    monkeypatch.setattr(
        cli,
        "get_team_links_from_league",
        lambda *args, **kwargs: [
            (f"{league_link}/1", "Team One"),
            (f"{league_link}/4", "Dekes and Geek(ie)s"),
        ],
    )
    monkeypatch.setattr(
        cli,
        "get_links_from_standings",
        lambda league_id, proxies, proxy=None: (
            [
                "https://hockey.fantasysports.yahoo.com/2025/hockey/19715/1",
                "https://hockey.fantasysports.yahoo.com/2025/hockey/19715/8",
            ],
            "proxy",
        ),
    )
    monkeypatch.setattr(
        cli,
        "inspect_team_link",
        lambda link, proxies, proxy=None: (
            ("Team One", proxy) if link.endswith("/1") else ("Dekes and Geek(ie)s", proxy)
        ),
    )

    result, proxy = cli.resolve_league_links(
        bs4.BeautifulSoup("<html></html>", "lxml"),
        league_link,
        "12922",
        season_mode,
        proxies=[],
        proxy=None,
    )

    assert result == (
        [],
        [
            f"{league_link}/1",
            f"{league_link}/4",
        ],
    )
    assert proxy == "proxy"
    assert cli.NO_MATCHUPS_FOUND_MESSAGE in capsys.readouterr().out


def test_resolve_league_links_skips_standings_team_with_empty_roster(monkeypatch, capsys):
    season_mode = cli.SEASON_MODES[cli.SEASON_CHOICES["preseason"]]
    league_link = "https://hockey.fantasysports.yahoo.com/hockey/12922"
    monkeypatch.setattr(cli, "get_links", lambda *args, **kwargs: ([], []))
    monkeypatch.setattr(
        cli,
        "get_team_links_from_league",
        lambda *args, **kwargs: [(f"{league_link}/1", "Team One")],
    )
    monkeypatch.setattr(
        cli,
        "get_links_from_standings",
        lambda league_id, proxies, proxy=None: (
            ["https://hockey.fantasysports.yahoo.com/2025/hockey/19715/8"],
            "proxy",
        ),
    )
    monkeypatch.setattr(
        cli,
        "inspect_team_link",
        lambda link, proxies, proxy=None: (None, proxy),
    )

    result, proxy = cli.resolve_league_links(
        bs4.BeautifulSoup("<html></html>", "lxml"),
        league_link,
        "12922",
        season_mode,
        proxies=[],
        proxy=None,
    )

    assert result == ([], [f"{league_link}/1"])
    assert cli.NO_MATCHUPS_FOUND_MESSAGE in capsys.readouterr().out


def test_resolve_league_links_keeps_in_season_error(monkeypatch, capsys):
    season_mode = cli.SEASON_MODES[cli.SEASON_CHOICES["in_season"]]
    monkeypatch.setattr(cli, "get_links", lambda *args, **kwargs: ([], []))

    result, proxy = cli.resolve_league_links(
        bs4.BeautifulSoup("<html></html>", "lxml"),
        "https://hockey.fantasysports.yahoo.com/hockey/19715",
        "19715",
        season_mode,
        proxies=[],
        proxy=None,
    )

    assert result is None
    assert proxy is None
    assert cli.LEAGUE_ID_INCORRECT_MESSAGE in capsys.readouterr().out


def test_get_links_from_standings_returns_team_hrefs(monkeypatch):
    captured = {}

    def fake_parse_full_page(link, proxies, proxy=None):
        captured["link"] = link
        captured["proxies"] = proxies
        captured["proxy"] = proxy
        return bs4.BeautifulSoup("<html></html>", "lxml"), proxy

    monkeypatch.setattr(cli, "parse_full_page", fake_parse_full_page)
    monkeypatch.setattr(
        cli,
        "scrape_from_page",
        lambda *args, **kwargs: [
            SimpleNamespace(get=lambda attr: "/team/10"),
            SimpleNamespace(get=lambda attr: "/team/11"),
        ],
    )

    result, proxy = cli.get_links_from_standings("19715", proxies=[])

    assert captured["link"] == cli.STANDINGS_PAGE_URL.format("19715")
    assert captured["proxies"] == []
    assert captured["proxy"] is None
    assert result == ["/team/10", "/team/11"]
    assert proxy is None


def test_season_modes_map_to_expected_flags():
    preseason = cli.SEASON_MODES[cli.SEASON_CHOICES["preseason"]]
    just_started = cli.SEASON_MODES[cli.SEASON_CHOICES["just_started"]]
    in_season = cli.SEASON_MODES[cli.SEASON_CHOICES["in_season"]]

    assert preseason.in_progress is False
    assert preseason.just_started is False
    assert just_started.in_progress is True
    assert just_started.just_started is True
    assert in_season.in_progress is True
    assert in_season.just_started is False


def test_prompt_season_mode_returns_selected_mode(monkeypatch):
    monkeypatch.setattr(
        cli,
        "validate_input",
        lambda *args, **kwargs: cli.SEASON_CHOICES["preseason"],
    )

    season_mode = cli.prompt_season_mode()

    assert season_mode == cli.SEASON_MODES[cli.SEASON_CHOICES["preseason"]]


def test_build_avg_stats_page_adds_last_season_when_just_started():
    assert cli.build_avg_stats_page(True) == {"stat1": "AS", "stat2": "AS_2025"}
    assert cli.build_avg_stats_page(False) == {"stat1": "AS"}
