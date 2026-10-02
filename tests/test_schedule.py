from types import SimpleNamespace
import datetime

import pytest

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


def test_get_remaining_week_end_returns_sunday():
    assert schedule.get_remaining_week_end(datetime.date(2026, 10, 1)) == datetime.date(2026, 10, 4)
    assert schedule.get_remaining_week_end(datetime.date(2026, 10, 4)) == datetime.date(2026, 10, 4)


def test_resolve_schedule_window_defaults_to_today():
    start_date, end_date = schedule.resolve_schedule_window(today=datetime.date(2026, 10, 1))

    assert start_date == datetime.date(2026, 10, 1)
    assert end_date == datetime.date(2026, 10, 4)


def test_resolve_schedule_window_applies_override_and_clamps_to_today():
    start_date, end_date = schedule.resolve_schedule_window(
        today=datetime.date(2026, 10, 1),
        start_date_override=datetime.date(2026, 9, 20),
    )

    assert start_date == datetime.date(2026, 10, 1)
    assert end_date == datetime.date(2026, 10, 4)


def test_resolve_schedule_window_override_in_future_shifts_window():
    start_date, end_date = schedule.resolve_schedule_window(
        today=datetime.date(2026, 10, 1),
        start_date_override=datetime.date(2026, 10, 2),
    )

    assert start_date == datetime.date(2026, 10, 2)
    assert end_date == datetime.date(2026, 10, 4)


def test_resolve_schedule_window_keeps_explicit_range_with_override():
    start_date, end_date = schedule.resolve_schedule_window(
        start_date=datetime.date(2026, 10, 1),
        end_date=datetime.date(2026, 10, 3),
        today=datetime.date(2026, 10, 1),
        start_date_override=datetime.date(2026, 10, 2),
    )

    assert start_date == datetime.date(2026, 10, 2)
    assert end_date == datetime.date(2026, 10, 3)


def test_resolve_schedule_window_resets_end_when_override_passes_it():
    start_date, end_date = schedule.resolve_schedule_window(
        start_date=datetime.date(2026, 4, 1),
        end_date=datetime.date(2026, 4, 4),
        today=datetime.date(2026, 4, 1),
        start_date_override=datetime.date(2026, 4, 10),
    )

    assert start_date == datetime.date(2026, 4, 10)
    assert end_date == datetime.date(2026, 4, 12)


def test_get_schedule_uses_nhl_api_by_default(monkeypatch):
    calls = []
    monkeypatch.setattr(
        schedule,
        "get_nhl_schedule",
        lambda **kwargs: calls.append(kwargs) or ({}, None),
    )

    result, proxy = schedule.get_schedule(
        start_date=datetime.date(2026, 10, 1),
        end_date=datetime.date(2026, 10, 3),
        start_date_override=datetime.date(2026, 10, 2),
    )

    assert result == {}
    assert proxy is None
    assert calls == [
        {
            "start_date": datetime.date(2026, 10, 1),
            "end_date": datetime.date(2026, 10, 3),
            "start_date_override": datetime.date(2026, 10, 2),
        }
    ]


def test_get_nhl_schedule_counts_future_games_and_applies_aliases(monkeypatch):
    payload = {
        "gameWeek": [
            {
                "date": "2026-10-01",
                "games": [
                    {
                        "gameState": "FUT",
                        "awayTeam": {"abbrev": "MTL"},
                        "homeTeam": {"abbrev": "BOS"},
                    },
                    {
                        "gameState": "OFF",
                        "awayTeam": {"abbrev": "MTL"},
                        "homeTeam": {"abbrev": "TOR"},
                    },
                ],
            },
            {
                "date": "2026-10-02",
                "games": [
                    {
                        "gameState": "FUT",
                        "awayTeam": {"abbrev": "SJS"},
                        "homeTeam": {"abbrev": "NJD"},
                    }
                ],
            },
        ]
    }
    urls = []

    def fake_get(url, timeout):
        urls.append(url)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

    monkeypatch.setattr(schedule.requests, "get", fake_get)

    result, proxy = schedule.get_nhl_schedule(
        start_date=datetime.date(2026, 10, 1),
        end_date=datetime.date(2026, 10, 3),
    )

    assert proxy is None
    assert urls == ["https://api-web.nhle.com/v1/schedule/2026-10-01"]
    assert result["BOS"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 1
    assert result["MTL"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 1
    assert result["MON"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 1
    assert result["SJS"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 1
    assert result["SJ"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 1
    assert result["NJD"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 1
    assert result["NJ"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 1
    assert "TOR" not in result


def test_get_nhl_schedule_skips_today_when_override_is_tomorrow(monkeypatch):
    payload = {
        "gameWeek": [
            {
                "date": "2026-10-01",
                "games": [
                    {
                        "gameState": "FUT",
                        "awayTeam": {"abbrev": "BOS"},
                        "homeTeam": {"abbrev": "TOR"},
                    }
                ],
            },
            {
                "date": "2026-10-02",
                "games": [
                    {
                        "gameState": "FUT",
                        "awayTeam": {"abbrev": "MTL"},
                        "homeTeam": {"abbrev": "OTT"},
                    }
                ],
            },
        ]
    }
    monkeypatch.setattr(
        schedule.requests,
        "get",
        lambda url, timeout: SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload),
    )

    result, _ = schedule.get_nhl_schedule(
        today=datetime.date(2026, 10, 1),
        start_date_override=datetime.date(2026, 10, 2),
    )

    assert "BOS" not in result
    assert "TOR" not in result
    assert result["MTL"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 1
    assert result["OTT"][schedule.GAMES_LEFT_THIS_WEEK_COLUMN] == 1


def test_get_nhl_schedule_ignores_games_outside_requested_range(monkeypatch):
    payload = {
        "gameWeek": [
            {
                "date": "2026-10-05",
                "games": [
                    {
                        "gameState": "FUT",
                        "awayTeam": {"abbrev": "BOS"},
                        "homeTeam": {"abbrev": "TOR"},
                    }
                ],
            }
        ]
    }
    monkeypatch.setattr(
        schedule.requests,
        "get",
        lambda url, timeout: SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload),
    )

    result, _ = schedule.get_nhl_schedule(
        start_date=datetime.date(2026, 10, 1),
        end_date=datetime.date(2026, 10, 2),
    )

    assert result == {}


def test_get_nhl_schedule_returns_empty_when_api_request_fails(monkeypatch):
    import requests as requests_module

    def raise_error():
        raise requests_module.HTTPError("503")

    monkeypatch.setattr(
        schedule.requests,
        "get",
        lambda url, timeout: SimpleNamespace(raise_for_status=raise_error, json=lambda: {}),
    )

    result, proxy = schedule.get_nhl_schedule(
        start_date=datetime.date(2026, 10, 1),
        end_date=datetime.date(2026, 10, 2),
    )

    assert result == {}
    assert proxy is None
