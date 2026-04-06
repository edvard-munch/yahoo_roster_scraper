from types import SimpleNamespace
import datetime

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
    monkeypatch.setattr(schedule.proxies, "get_response", lambda *args, **kwargs: response)

    result, _ = schedule.get_schedule(proxies_list=[])

    assert result["BOS"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 3
    assert result["MON"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 2
    assert result["MTL"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 2
    assert result["SJ"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 1
    assert result["SJS"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 1


def test_get_schedule_returns_empty_when_schedule_table_missing(monkeypatch):
    html = "<html><body><table><tr><th>Something</th></tr></table></body></html>"
    response = SimpleNamespace(content=html.encode("utf-8"))
    monkeypatch.setattr(schedule.proxies, "get_response", lambda *args, **kwargs: response)

    result, _ = schedule.get_schedule(proxies_list=[])

    assert result == {}


def test_get_schedule_with_proxies_uses_retry_helper(monkeypatch, frozenpool_schedule_html):
    response = SimpleNamespace(content=frozenpool_schedule_html.encode("utf-8"))
    calls = []

    def fake_get_response_with_retries(url, params, proxies_list, failure_target, proxy=None):
        calls.append(
            {
                "url": url,
                "params": params,
                "proxies_list": proxies_list,
                "failure_target": failure_target,
                "proxy": proxy,
            }
        )
        return response, {"http": "1.1.1.1:80", "https": "1.1.1.1:80"}

    monkeypatch.setattr(
        schedule.proxies,
        "get_response_with_retries",
        fake_get_response_with_retries,
    )

    result, _ = schedule.get_schedule(proxies_list=[{"http": "proxy", "https": "proxy"}])

    assert result["BOS"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 3
    assert len(calls) == 1
    assert calls[0]["failure_target"] == schedule.proxies.PROXY_FAILURE_TARGET_SCHEDULE


def test_get_schedule_uses_override_url_when_provided(monkeypatch, frozenpool_schedule_html):
    response = SimpleNamespace(content=frozenpool_schedule_html.encode("utf-8"))
    calls = []

    monkeypatch.setattr(
        schedule.proxies,
        "get_response",
        lambda url, params: calls.append({"url": url, "params": params}) or response,
    )

    schedule.get_schedule(
        proxies_list=[],
        schedule_url="https://example.com/custom-schedule",
    )

    assert calls[0]["url"] == "https://example.com/custom-schedule"


def test_build_schedule_url_uses_date_range_when_provided():
    result = schedule.build_schedule_url(
        start_date=datetime.date(2026, 3, 25),
        end_date=datetime.date(2026, 4, 2),
    )

    assert "report=Custom" in result
    assert "startdate=2026-03-25" in result
    assert "enddate=2026-04-02" in result


def test_build_schedule_url_keeps_override_and_applies_range():
    result = schedule.build_schedule_url(
        schedule_url="https://example.com/path?report=Remaining+wk",
        start_date=datetime.date(2026, 5, 1),
        end_date=datetime.date(2026, 5, 10),
    )

    assert result.startswith("https://example.com/path?")
    assert "report=Custom" in result
    assert "startdate=2026-05-01" in result
    assert "enddate=2026-05-10" in result


def test_get_schedule_with_proxies_returns_empty_on_retry_runtime_error(monkeypatch):
    printed = []

    monkeypatch.setattr(
        "builtins.print",
        lambda *args, **kwargs: printed.append(" ".join(str(arg) for arg in args)),
    )
    monkeypatch.setattr(
        schedule.proxies,
        "get_response_with_retries",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("proxy retry failed")),
    )

    result, _ = schedule.get_schedule(proxies_list=[{"http": "proxy", "https": "proxy"}])

    assert result == {}
    assert any("proxy retry failed" in message for message in printed)
