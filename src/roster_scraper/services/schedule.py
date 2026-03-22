import re

import bs4

from . import proxies


SCHEDULE_URL = (
    "https://frozenpool.dobbersports.com/frozenpool_planner.php?"
    "report=Remaining+wk&startdate=&enddate=&light_day=8&include_preseason=y"
)
PARSER = "lxml"
GAMES_LEFT_THIS_WEEK_COLUMN = "GL"
SHEDULE_SCRAPING_SUCCESS_MESSAGE = "Schedule scraped!"
SCHEDULE_DEBUG_PREVIEW_TEAMS = 10
SCHEDULE_NOT_AVAILABLE_MESSAGE = "Schedule table not found on source page."
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


def get_schedule(proxies_list, proxy=None):
    params = {}
    if proxies_list:
        try:
            web, proxy = proxies.get_response_with_retries(
                SCHEDULE_URL,
                params,
                proxies_list,
                max_retries=proxies.DEFAULT_PROXY_MAX_RETRIES,
                failure_target=proxies.PROXY_FAILURE_TARGET_SCHEDULE,
                proxy=proxy,
            )
        except RuntimeError as err:
            print(err)
            return {}, None
    else:
        web = proxies.get_response(SCHEDULE_URL, params)

    soup = bs4.BeautifulSoup(web.content, PARSER)
    team_schedules = {}
    schedule_table = None

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        headers = [cell.get_text(strip=True) for cell in rows[1].find_all(["th", "td"])]
        if len(headers) >= 2 and headers[0] == "Team" and headers[1] == "GP":
            schedule_table = table
            break

    if not schedule_table:
        print(SCHEDULE_NOT_AVAILABLE_MESSAGE)
        return team_schedules, proxy

    rows = schedule_table.find_all("tr")[2:]
    for row in rows:
        cells = [cell.get_text(strip=True) for cell in row.find_all(["th", "td"])]
        if len(cells) < 2:
            continue

        team_code = normalize_team_code(cells[0])
        games_match = re.search(r"\d+", cells[1])

        if not re.fullmatch(r"[A-Z]{2,4}", team_code):
            continue

        games_left = int(games_match.group(0)) if games_match else 0
        team_schedules[team_code] = {GAMES_LEFT_THIS_WEEK_COLUMN: games_left}

    raw_team_count = len(team_schedules)
    team_schedules = apply_team_aliases(team_schedules)
    loaded_team_count = len(team_schedules)
    alias_entries_added = loaded_team_count - raw_team_count

    print(SHEDULE_SCRAPING_SUCCESS_MESSAGE)
    print(SCHEDULE_TEAMS_SCRAPED_MESSAGE.format(raw_team_count))
    print(SCHEDULE_TEAMS_LOADED_MESSAGE.format(loaded_team_count))
    if alias_entries_added:
        print(SCHEDULE_ALIAS_ENTRIES_ADDED_MESSAGE.format(alias_entries_added))
    preview = sorted(team_schedules.keys())[:SCHEDULE_DEBUG_PREVIEW_TEAMS]
    print(f"Schedule teams preview: {preview}")
    return team_schedules, proxy
