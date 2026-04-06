import datetime

import bs4

from roster_scraper import cli


def test_parse_matchup_date_range_text_same_month_without_year_uses_default_year():
    result = cli.parse_matchup_date_range_text(
        "Matchup Mar 25 - 31",
        today=datetime.date(2026, 3, 1),
    )

    assert result == (datetime.date(2026, 3, 25), datetime.date(2026, 3, 31))


def test_parse_matchup_date_range_text_cross_month_with_year():
    result = cli.parse_matchup_date_range_text(
        "Playoff window Mar 25, 2026 - Apr 4, 2026",
    )

    assert result == (datetime.date(2026, 3, 25), datetime.date(2026, 4, 4))


def test_parse_matchup_date_range_from_soup_returns_none_when_not_found():
    soup = bs4.BeautifulSoup("<html><body>No range here</body></html>", "lxml")

    result = cli.parse_matchup_date_range_from_soup(soup)

    assert result is None


def test_get_matchup_date_range_returns_parsed_range_and_proxy(monkeypatch):
    soup = bs4.BeautifulSoup("<html><body>Round Apr 1 - Apr 9</body></html>", "lxml")
    current_proxy = {"http": "1.1.1.1:80", "https": "1.1.1.1:80"}

    monkeypatch.setattr(cli, "parse_full_page", lambda *args, **kwargs: (soup, current_proxy))

    date_range, proxy = cli.get_matchup_date_range(
        "https://example.com/matchup/1",
        proxies=[],
        today=datetime.date(2026, 4, 1),
    )

    assert date_range == (datetime.date(2026, 4, 1), datetime.date(2026, 4, 9))
    assert proxy == current_proxy


def test_extract_matchup_week_from_query_string():
    result = cli.extract_matchup_week(
        "https://hockey.fantasysports.yahoo.com/hockey/10524/matchup?week=24&mid1=1&mid2=12"
    )

    assert result == 24


def test_parse_matchup_date_range_from_league_soup_uses_week_block():
    soup = bs4.BeautifulSoup(
        "<html><body>Week 23: Mar 30 - Apr 5 Week 24: Apr 6 - Apr 16 Week 25: Apr 17 - Apr 23</body></html>",
        "lxml",
    )

    result = cli.parse_matchup_date_range_from_league_soup(
        soup,
        matchup_week=24,
        today=datetime.date(2026, 4, 1),
    )

    assert result == (datetime.date(2026, 4, 6), datetime.date(2026, 4, 16))


def test_get_matchup_date_range_falls_back_to_league_soup_when_matchup_page_has_no_dates(
    monkeypatch,
):
    matchup_soup = bs4.BeautifulSoup("<html><body>Week 24</body></html>", "lxml")
    league_soup = bs4.BeautifulSoup(
        "<html><body>Week 24: Apr 6 - Apr 16 Week 25: Apr 17 - Apr 23</body></html>",
        "lxml",
    )

    monkeypatch.setattr(cli, "parse_full_page", lambda *args, **kwargs: (matchup_soup, None))

    date_range, _ = cli.get_matchup_date_range(
        "https://hockey.fantasysports.yahoo.com/hockey/10524/matchup?week=24&mid1=1&mid2=12",
        proxies=[],
        today=datetime.date(2026, 4, 1),
        league_soup=league_soup,
    )

    assert date_range == (datetime.date(2026, 4, 6), datetime.date(2026, 4, 16))
