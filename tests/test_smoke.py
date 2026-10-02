from roster_scraper.services import schedule


def test_yahoo_fixture_html_is_loaded(yahoo_team_page_html):
    assert "Yahoo Fantasy Sports" in yahoo_team_page_html


def test_schedule_aliases_available():
    assert schedule.TEAM_CODE_ALIASES["MON"] == "MTL"
