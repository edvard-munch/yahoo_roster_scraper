import datetime
import re

import requests


GAMES_LEFT_THIS_WEEK_COLUMN = "GL"
NHL_SCHEDULE_API_URL = "https://api-web.nhle.com/v1/schedule/{}"
NHL_SCHEDULE_REQUEST_TIMEOUT = 15
NHL_SCHEDULE_SOURCE_MESSAGE = "NHL schedule API range: {} -> {}"
NHL_SCHEDULE_LOAD_FAILED_MESSAGE = "Could not load NHL schedule for {}: {}"
FUTURE_GAME_STATE = "FUT"
SCHEDULE_DEBUG_PREVIEW_TEAMS = 10
SCHEDULE_TEAMS_SCRAPED_MESSAGE = "Schedule teams scraped (raw): {}"
SCHEDULE_TEAMS_LOADED_MESSAGE = "Schedule teams loaded (after aliases): {}"
SCHEDULE_ALIAS_ENTRIES_ADDED_MESSAGE = "Schedule alias entries added: {}"
TEAM_CODE_ALIASES = {
    "MON": "MTL",
    "ANH": "ANA",
    "NJ": "NJD",
    "LA": "LAK",
    "CLS": "CBJ",
    "SJ": "SJS",
    "TB": "TBL",
    "WAS": "WSH",
}


def normalize_team_code(code):
    return re.sub(r"[^A-Z]", "", code.upper())


def apply_team_aliases(team_schedules):
    for source_code, target_code in TEAM_CODE_ALIASES.items():
        source_data = team_schedules.get(source_code)
        target_data = team_schedules.get(target_code)

        if source_data and not target_data:
            team_schedules[target_code] = dict(source_data)
        elif target_data and not source_data:
            team_schedules[source_code] = dict(target_data)

    return team_schedules


def get_remaining_week_end(today=None):
    today = today or datetime.date.today()
    days_until_sunday = (6 - today.weekday()) % 7
    return today + datetime.timedelta(days=days_until_sunday)


def resolve_schedule_window(start_date=None, end_date=None, today=None, start_date_override=None):
    today = today or datetime.date.today()

    if start_date_override:
        start_date = max(start_date_override, today)

    if not start_date:
        start_date = today

    if not end_date:
        end_date = get_remaining_week_end(start_date)

    if end_date < start_date:
        end_date = get_remaining_week_end(start_date)

    return start_date, end_date


def fetch_nhl_schedule(start_date, end_date):
    team_games = {}
    current_week_start = start_date

    while current_week_start <= end_date:
        try:
            response = requests.get(
                NHL_SCHEDULE_API_URL.format(current_week_start.isoformat()),
                timeout=NHL_SCHEDULE_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as err:
            print(NHL_SCHEDULE_LOAD_FAILED_MESSAGE.format(current_week_start, err))
            current_week_start += datetime.timedelta(days=7)
            continue

        for day in payload.get("gameWeek", []):
            try:
                day_date = datetime.date.fromisoformat(day["date"])
            except (KeyError, ValueError):
                continue

            if not start_date <= day_date <= end_date:
                continue

            for game in day.get("games", []):
                if game.get("gameState") != FUTURE_GAME_STATE:
                    continue

                for side in ("awayTeam", "homeTeam"):
                    team_code = game.get(side, {}).get("abbrev")
                    if team_code:
                        team_games[team_code] = team_games.get(team_code, 0) + 1

        current_week_start += datetime.timedelta(days=7)

    return team_games


def get_nhl_schedule(start_date=None, end_date=None, today=None, start_date_override=None):
    start_date, end_date = resolve_schedule_window(
        start_date=start_date,
        end_date=end_date,
        today=today,
        start_date_override=start_date_override,
    )

    print(NHL_SCHEDULE_SOURCE_MESSAGE.format(start_date, end_date))

    team_games = fetch_nhl_schedule(start_date, end_date)

    raw_team_count = len(team_games)
    team_schedules = {
        team_code: {GAMES_LEFT_THIS_WEEK_COLUMN: games} for team_code, games in team_games.items()
    }
    team_schedules = apply_team_aliases(team_schedules)
    loaded_team_count = len(team_schedules)
    alias_entries_added = loaded_team_count - raw_team_count

    print(SCHEDULE_TEAMS_SCRAPED_MESSAGE.format(raw_team_count))
    print(SCHEDULE_TEAMS_LOADED_MESSAGE.format(loaded_team_count))
    if alias_entries_added:
        print(SCHEDULE_ALIAS_ENTRIES_ADDED_MESSAGE.format(alias_entries_added))
    preview = sorted(team_schedules.keys())[:SCHEDULE_DEBUG_PREVIEW_TEAMS]
    print(f"Schedule teams preview: {preview}")
    return team_schedules, None


def get_schedule(start_date=None, end_date=None, start_date_override=None):
    return get_nhl_schedule(
        start_date=start_date,
        end_date=end_date,
        start_date_override=start_date_override,
    )
