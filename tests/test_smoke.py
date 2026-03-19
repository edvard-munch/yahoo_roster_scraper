from roster_scraper.services import schedule


def test_fixture_html_is_loaded(frozenpool_schedule_html, yahoo_team_page_html):
    assert "Team" in frozenpool_schedule_html
    assert "Yahoo Fantasy Sports" in yahoo_team_page_html


def test_schedule_aliases_available():
    assert schedule.TEAM_CODE_ALIASES["MON"] == "MTL"
