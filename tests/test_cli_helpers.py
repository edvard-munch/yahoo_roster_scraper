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

    def fake_get_response_with_retries(link, params, proxies, max_retries, failure_target, proxy):
        calls["link"] = link
        calls["params"] = params
        calls["proxies"] = proxies
        calls["max_retries"] = max_retries
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
    assert calls["max_retries"] == cli.proxies_scraper.DEFAULT_PROXY_MAX_RETRIES
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


def test_get_links_returns_none_when_no_matchups_found():
    soup = bs4.BeautifulSoup("<html><body><p>empty</p></body></html>", "lxml")

    links = cli.get_links(soup, "https://hockey.fantasysports.yahoo.com/hockey/19715")

    assert links is None


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
