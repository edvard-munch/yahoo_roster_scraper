from types import SimpleNamespace

from roster_scraper.services import schedule


def test_normalize_team_code_strips_non_letters_and_uppercases():
    assert schedule.normalize_team_code(" sj* ") == "SJ"


def test_apply_team_aliases_adds_target_from_source():
    team_schedules = {"MON": {schedule.GAMES_LEFT_THIS_WEEK_COLUMN: 2}}

    result = schedule.apply_team_aliases(team_schedules)

    assert result["MON"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 2
    assert result["MTL"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 2


def test_apply_team_aliases_adds_source_from_target():
    team_schedules = {"MTL": {schedule.GAMES_LEFT_THIS_WEEK_COLUMN: 4}}

    result = schedule.apply_team_aliases(team_schedules)

    assert result["MTL"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 4
    assert result["MON"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 4


def test_get_schedule_parses_fixture_html_and_applies_aliases(
    monkeypatch, frozenpool_schedule_html
):
    response = SimpleNamespace(content=frozenpool_schedule_html.encode("utf-8"))
    monkeypatch.setattr(
        schedule.proxies, "get_response", lambda *args, **kwargs: response
    )

    result = schedule.get_schedule(proxies_list=[])

    assert result["BOS"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 3
    assert result["MON"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 2
    assert result["MTL"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 2
    assert result["SJ"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 1
    assert result["SJS"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 1


def test_get_schedule_returns_empty_when_schedule_table_missing(monkeypatch):
    html = "<html><body><table><tr><th>Something</th></tr></table></body></html>"
    response = SimpleNamespace(content=html.encode("utf-8"))
    monkeypatch.setattr(
        schedule.proxies, "get_response", lambda *args, **kwargs: response
    )

    result = schedule.get_schedule(proxies_list=[])

    assert result == {}
