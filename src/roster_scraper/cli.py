import bs4
import json
import os
import num2words
import re
import sys
import subprocess
import datetime
import xlsxwriter

from roster_scraper.services import positions as positions_scraper
from roster_scraper.services import proxies as proxies_scraper
from roster_scraper.services import schedule as schedule_scraper
from roster_scraper.services import matchups as matchups_service
from roster_scraper.services import roster_workflow
from roster_scraper.services import write_to_google_sheet
from roster_scraper.core import output as core_output
from roster_scraper.core import parsing as core_parsing


BASE_FANTASY_URL = "https://hockey.fantasysports.yahoo.com/hockey/"
SEASON_IN_PROGRESS = True
SEASON_JUST_STARTED = (
    False  # if stats are not representative enough yet, use stats from the last season
)

AVG_STATS_PAGE = {
    "stat1": "AS",
}

if SEASON_JUST_STARTED:
    AVG_STATS_PAGE["stat2"] = "AS_2025"  # Calculate year programmatically

if SEASON_IN_PROGRESS:
    START_FROM = 1
    NAME_COLUMN = 1
else:
    START_FROM = 1
    NAME_COLUMN = 0

PROXY_CHOICES = {"Y": True, "n": False}
FORMAT_CHOICES = {"xlsx": "1", "txt": "2", "json": "3", "google_sheets": "4"}

PARSER = "lxml"

NUMBER_OF_TEAMS_PROCESSED_MESSAGE = "{}/{} teams ready"
NUMBER_OF_MATCHUPS_PROCESSED_MESSAGE = "{}/{} matchups ready"
FORMAT_CHOICE_MESSAGE = (
    "Input 1 for full stats xls tables\n"
    "Input 2 for simple txt rosters\n"
    "Input 3 for positions in JSON file\n"
    "Input 4 for writing positions to Google Sheets:\n"
)

PROXIES_CHOICE_MESSAGE = "Use proxies? Y/n:\n"
INPUT_LEAGUE_ID_MESSAGE = "Input league's ID:\n"
INPUT_SCHEDULE_URL_MESSAGE = "Input schedule URL override (Enter for default):\n"
INCORRECT_CHOICE_MESSAGE = "Please select a correct option"
LEAGUE_ID_INCORRECT_MESSAGE = "League with this ID does not exist or not publicly viewable"
LEAGUE_SCRAPING_SUCCESS_MESSAGE = "League's main page scraped!"

TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"
XLSX_FILENAME_TEMPLATE = "reports/stats_list_{}.xlsx"
TXT_FILENAME = "reports/clean_rosters.txt"
POSITIONS_FILENAME = "reports/positions.json"
TEAM_NAME_HEADER = "--------------- {} ---------------"
MATCHUPS_WORKSHEET_NAME = "MATCHUPS"

MATCHUP_CLASSES = "Linkable Listitem No-p"
TEAMS_IN_MATCHUP_CLASSES = "Fz-sm.Phone-fz-xs.Ell"
MATCHUP_RESULT_CLASSES = "Table-plain Table Table-px-sm Table-mid Datatable Ta-center Tz-xxs Bdr"
TEAM_NAME_MATCHUP_RESULT_CLASSES = "Grid-u Nowrap"
HEADERS_CLASSES = "Alt Last"
TEAM_NAME_CLASSES = "Navtarget No-pbot F-reset No-case Fz-35 Fw-b team-name"
TEAM_NAME_STANDINGS_CLASSES = "Grid-u F-reset Ell Mawpx-250"
PLAYOFFS_HEADER = "Championship Bracket"
MATCHUP_DATE_RANGE_PATTERNS = [
    re.compile(
        r"(?P<start_month>[A-Za-z]{3,9})\s+(?P<start_day>\d{1,2})(?:,\s*(?P<start_year>\d{4}))?\s*-\s*(?P<end_month>[A-Za-z]{3,9})\s+(?P<end_day>\d{1,2})(?:,\s*(?P<end_year>\d{4}))?"
    ),
    re.compile(
        r"(?P<start_month>[A-Za-z]{3,9})\s+(?P<start_day>\d{1,2})(?:,\s*(?P<start_year>\d{4}))?\s*-\s*(?P<end_day>\d{1,2})(?:,\s*(?P<end_year>\d{4}))?"
    ),
]
MATCHUP_WEEK_QUERY_PATTERN = re.compile(r"[?&]week=(?P<week>\d+)")
MATCHUP_WEEK_BLOCK_PATTERN_TEMPLATE = r"Week\s+{week}\s*:\s*(?P<range>.*?)(?:" r"Week\s+\d+\s*:|$)"
MATCHUP_DATE_FORMATS = ("%b %d %Y", "%B %d %Y")
STANDINGS_PAGE_URL = (
    "https://hockey.fantasysports.yahoo.com/hockey/{}?module=standings&lhst=stand#lhststand"
)
EMPTY_SPOT_CLASSES = "Nowrap emptyplayer Inlineblock"
SPOT_CLASS = "pos-label"
PLAYER_NAME_CLASS = "player"
PLAYER_LINK_CLASSES = "Nowrap name F-link playernote"
TEAM_AND_POSITION_SPAN_CLASS = "Fz-xxs"

MATCHUP_TOTALS_PARAMETER = "&date=total"
MATCHUP_RANGE_DAYS_THRESHOLD = 7
SCHEDULE_URL_OVERRIDE_MESSAGE = "Using schedule URL override: {}"
MATCHUP_RANGE_DETECTED_MESSAGE = "Detected matchup range: {} -> {} ({} days)"
MATCHUP_RANGE_MODE_MESSAGE = "Using matchup range for schedule scraping"
MATCHUP_WEEKLY_MODE_MESSAGE = "Using default weekly schedule scraping"
MATCHUP_RANGE_NOT_FOUND_MESSAGE = (
    "Could not detect matchup date range; using default weekly schedule ({})"
)
EMPTY_SPOT_STRING = "Empty"
EMPTY_CELL = "-"

RESEARCH_STATS_PAGE = {
    "stat1": "R",
}

OPPONENTS_PAGE = {
    "stat1": "O",
}

INVALID_EXCEL_CHARACTERS_PATTERN = r"[*\\\/]"
EMPTY_STRING_PATTERN = r"^-$"

PLATFORMS = {
    "Windows": "win32",
    "Mac_OS": "darwin",
}

FILE_OPENERS = {"Linux": "xdg-open", "Mac_OS": "open"}

POSITION_CODES = ["G", "D", "LW", "RW", "C"]
NOT_PLAYING = ["IR", "IR+", "NA"]
PRESEASON = 1
SEASON = 2

WIDE_COLUMN_WIDTH = 20
NUMBER_OF_COLUMNS = 15
COLUMNS = {num2words.num2words(i + 1, to="ordinal"): (i, i) for i in range(NUMBER_OF_COLUMNS)}

START_HEADERS = {"Spot": [], "Forwards/Defensemen": [], "Team": [], "Pos": []}

SCORING_COLUMNS = [
    "G",
    "A",
    "P",
    "+/-",
    "PIM",
    "PPP",
    "PPG",
    "PPA",
    "SHP",
    "GWG",
    "SOG",
    "FW",
    "HIT",
    "BLK",
]
COLUMNS_TO_DELETE = ["Action", "Add", "Opp", "Status", "Pre-Season", "Current", "% Started"]


def scrape_from_page(soup, element_type, attr_type, attr_name):
    return soup.find_all(element_type, {attr_type: attr_name})


def get_team_name(soup, fallback_name="Unknown Team"):
    def clean_name(name):
        return re.sub(r"[\ue000-\uf8ff]", "", name).strip()[:30]

    name_links = scrape_from_page(soup, "span", "class", re.compile(TEAM_NAME_CLASSES))
    if name_links:
        return clean_name(name_links[0].text)

    fallback_name_span = soup.select_one("span.F-reset.Nowrap")
    if fallback_name_span:
        return clean_name(fallback_name_span.get_text(strip=True))

    title = soup.title.get_text(strip=True) if soup.title else None
    if title:
        title_text = title.split("|")[0].strip()
        if " - " in title_text:
            return clean_name(title_text.split(" - ", 1)[1])
        return clean_name(title_text)

    return fallback_name[:30]


def get_headers(soup):
    header_row = soup.find("tr", class_=HEADERS_CLASSES)

    if not header_row:
        for row in soup.find_all("tr"):
            header_names = [cell.get_text(strip=True) for cell in row.find_all(["th", "td"])]
            if "Action" in header_names:
                header_row = row
                break

    if not header_row:
        raise RuntimeError("Roster header row not found")

    headers = {**START_HEADERS, **{}}

    start_adding = False

    for child in header_row.find_all(["th", "td"]):
        name = child.get_text(strip=True)

        if SEASON_IN_PROGRESS:
            headers["Add"] = []

        if name == "Action":
            start_adding = True

        if start_adding:
            headers[name] = []

    headers[schedule_scraper.GAMES_LEFT_THIS_WEEK_COLUMN] = []

    return headers


def get_body(soup, schedule, missing_schedule_teams=None):
    skater_rows = soup.find_all("tbody")[1].find_all("tr")

    cell_values = []

    for i, row in enumerate(skater_rows):
        empty = row.find(class_=EMPTY_SPOT_CLASSES)
        index = 0

        if SEASON_IN_PROGRESS:
            spot = row.find(class_=SPOT_CLASS)

            if spot.string in NOT_PLAYING:
                continue

        for cell in row:
            if i == 0:
                cell_values.append([])

            if PLAYER_NAME_CLASS in cell.attrs["class"]:
                if i == 0:
                    cell_values.extend(([], []))
                player_link = cell.find(class_=PLAYER_LINK_CLASSES)
                if player_link:
                    name = player_link.string
                    span = cell.find(lambda tag: tag.get("class") == [TEAM_AND_POSITION_SPAN_CLASS])
                    team, position = span.string.split(" - ")

                    cell_values[index].append(name)
                    cell_values[index + 1].append(team)
                    cell_values[index + 2].append(position)
                    index += 3
                else:
                    cell_values[index].append(EMPTY_CELL)
                    cell_values[index + 1].append(EMPTY_CELL)
                    cell_values[index + 2].append(EMPTY_CELL)
                    index += 3

            else:
                if empty and (index > 0):
                    cell_values[index].append(EMPTY_CELL)

                else:
                    cell_values[index].append(cell.string)

                index += 1

        if i == 0:
            cell_values.append([])

        if empty:
            cell_values[index].append(0)
        else:
            if not schedule:
                cell_values[index].append(0)
                continue

            team_code = team.upper()
            mapped_team_code = schedule_scraper.TEAM_CODE_ALIASES.get(team_code, team_code)

            if team_code in schedule:
                cell_values[index].append(
                    schedule[team_code][schedule_scraper.GAMES_LEFT_THIS_WEEK_COLUMN]
                )
            elif mapped_team_code in schedule:
                cell_values[index].append(
                    schedule[mapped_team_code][schedule_scraper.GAMES_LEFT_THIS_WEEK_COLUMN]
                )
            else:
                if missing_schedule_teams is not None:
                    missing_schedule_teams.add(team_code)
                cell_values[index].append(0)

    return cell_values


def parse_full_page(link, proxies, proxy=None, params=None):
    if params is None:
        params = {}

    if proxies:
        web, proxy = proxies_scraper.get_response_with_retries(
            link,
            params,
            proxies,
            failure_target=proxies_scraper.PROXY_FAILURE_TARGET_PAGE,
            proxy=proxy,
        )

    else:
        web = proxies_scraper.get_response(link, params)

    return (bs4.BeautifulSoup(web.text, PARSER), proxy)


def validate_input(message, choices):
    choice = input(message)

    if choice in choices:
        return choice
    else:
        print(INCORRECT_CHOICE_MESSAGE)
        return None


def get_links(soup, league_link):
    matchups = scrape_from_page(soup, "li", "class", re.compile(MATCHUP_CLASSES))

    if matchups:
        matchup_links = []
        team_links = []

        for match in matchups:
            matchup_links.append(f"{league_link}/{match.attrs['data-target'].split('/')[-1]}")
            teams = match.select(f"div.{TEAMS_IN_MATCHUP_CLASSES}")

            for team in teams:
                html_link = team.find("a")
                base_team_url = html_link.get("href")
                team_links.append(base_team_url)

        print(LEAGUE_SCRAPING_SUCCESS_MESSAGE)
        return (matchup_links, team_links)

    else:
        print(LEAGUE_ID_INCORRECT_MESSAGE)
        return None


def get_links_from_standings(league_id, proxies, proxy=None):
    standings_page_soup, proxy = parse_full_page(
        STANDINGS_PAGE_URL.format(league_id), proxies, proxy
    )
    teams = scrape_from_page(standings_page_soup, "a", "class", TEAM_NAME_STANDINGS_CLASSES)
    return [team_link.get("href") for team_link in teams], proxy


def _build_matchup_date(month, day, year):
    for fmt in MATCHUP_DATE_FORMATS:
        try:
            return datetime.datetime.strptime(f"{month} {day} {year}", fmt).date()
        except ValueError:
            continue
    return None


def parse_matchup_date_range_text(raw_text, today=None):
    if not raw_text:
        return None

    default_year = (today or datetime.date.today()).year

    for pattern in MATCHUP_DATE_RANGE_PATTERNS:
        match = pattern.search(raw_text)
        if not match:
            continue

        groups = match.groupdict()
        start_month = groups["start_month"]
        start_day = groups["start_day"]
        start_year = int(groups.get("start_year") or groups.get("end_year") or default_year)

        end_month = groups.get("end_month") or start_month
        end_day = groups["end_day"]
        end_year = int(groups.get("end_year") or start_year)

        start_date = _build_matchup_date(start_month, start_day, start_year)
        end_date = _build_matchup_date(end_month, end_day, end_year)

        if start_date and end_date:
            return start_date, end_date

    return None


def parse_matchup_date_range_from_soup(soup, today=None):
    if not soup:
        return None
    return parse_matchup_date_range_text(soup.get_text(" ", strip=True), today=today)


def extract_matchup_week(matchup_link):
    if not matchup_link:
        return None

    week_match = MATCHUP_WEEK_QUERY_PATTERN.search(matchup_link)
    if not week_match:
        return None

    return int(week_match.group("week"))


def parse_matchup_date_range_from_league_soup(league_soup, matchup_week, today=None):
    if not league_soup or not matchup_week:
        return None

    text = league_soup.get_text(" ", strip=True)
    week_pattern = re.compile(
        MATCHUP_WEEK_BLOCK_PATTERN_TEMPLATE.format(week=matchup_week),
        re.IGNORECASE,
    )
    week_match = week_pattern.search(text)
    if not week_match:
        return None

    return parse_matchup_date_range_text(week_match.group("range"), today=today)


def get_matchup_date_range(matchup_link, proxies, proxy=None, today=None, league_soup=None):
    soup, proxy = parse_full_page(matchup_link, proxies, proxy)
    date_range = parse_matchup_date_range_from_soup(soup, today=today)

    if date_range:
        return date_range, proxy

    matchup_week = extract_matchup_week(matchup_link)
    date_range = parse_matchup_date_range_from_league_soup(league_soup, matchup_week, today=today)

    return date_range, proxy


def build_roster_context(workbook, matchups_context):
    return roster_workflow.RosterWorkflowContext(
        format_choices=FORMAT_CHOICES,
        parser=PARSER,
        proxies_scraper=proxies_scraper,
        schedule_scraper=schedule_scraper,
        core_parsing=core_parsing,
        core_output=core_output,
        write_to_google_sheet=write_to_google_sheet,
        workbook=workbook,
        scoring_columns=SCORING_COLUMNS,
        empty_spot_string=EMPTY_SPOT_STRING,
        number_of_teams_processed_message=NUMBER_OF_TEAMS_PROCESSED_MESSAGE,
        positions_filename=POSITIONS_FILENAME,
        get_team_name=get_team_name,
        get_headers=get_headers,
        get_body=get_body,
        matchups_service=matchups_service,
        matchups_context=matchups_context,
    )


def main():
    use_proxies_choice = validate_input(PROXIES_CHOICE_MESSAGE, PROXY_CHOICES)

    while not use_proxies_choice:
        use_proxies_choice = validate_input(PROXIES_CHOICE_MESSAGE, PROXY_CHOICES)

    use_proxies = PROXY_CHOICES[use_proxies_choice]

    if use_proxies:
        proxies = proxies_scraper.scrape_proxies()
    else:
        proxies = []

    league_id = input(INPUT_LEAGUE_ID_MESSAGE)

    link = BASE_FANTASY_URL + league_id
    main_page_soup, current_proxy = parse_full_page(link, proxies)
    league_scrapable = get_links(main_page_soup, link)

    while not league_scrapable:
        league_id = input(INPUT_LEAGUE_ID_MESSAGE)
        link = BASE_FANTASY_URL + league_id
        main_page_soup, current_proxy = parse_full_page(link, proxies, current_proxy)
        league_scrapable = get_links(main_page_soup, link)

    team_links = league_scrapable[1]

    choice = validate_input(FORMAT_CHOICE_MESSAGE, FORMAT_CHOICES.values())
    while not choice:
        choice = validate_input(FORMAT_CHOICE_MESSAGE, FORMAT_CHOICES.values())

    matchups_context = matchups_service.MatchupsContext(
        columns=COLUMNS,
        wide_column_width=WIDE_COLUMN_WIDTH,
        number_of_matchups_processed_message=NUMBER_OF_MATCHUPS_PROCESSED_MESSAGE,
        matchup_totals_parameter=MATCHUP_TOTALS_PARAMETER,
        matchup_result_classes=MATCHUP_RESULT_CLASSES,
        team_name_matchup_result_classes=TEAM_NAME_MATCHUP_RESULT_CLASSES,
        proxies_scraper=proxies_scraper,
        parse_full_page=parse_full_page,
        scrape_from_page=scrape_from_page,
    )

    if choice == FORMAT_CHOICES["xlsx"]:
        matchup_links = league_scrapable[0]

        schedule_url = input(INPUT_SCHEDULE_URL_MESSAGE).strip()
        schedule_url_override = schedule_url or None

        if schedule_url_override:
            print(SCHEDULE_URL_OVERRIDE_MESSAGE.format(schedule_url_override))

        start_date = None
        end_date = None
        if not schedule_url_override and matchup_links:
            matchup_date_range, current_proxy = get_matchup_date_range(
                matchup_links[0],
                proxies,
                current_proxy,
                league_soup=main_page_soup,
            )
            if matchup_date_range:
                parsed_start_date, parsed_end_date = matchup_date_range
                duration_days = (parsed_end_date - parsed_start_date).days + 1
                print(
                    MATCHUP_RANGE_DETECTED_MESSAGE.format(
                        parsed_start_date,
                        parsed_end_date,
                        duration_days,
                    )
                )
                if duration_days > MATCHUP_RANGE_DAYS_THRESHOLD:
                    start_date = parsed_start_date
                    end_date = parsed_end_date
                    print(MATCHUP_RANGE_MODE_MESSAGE)
                else:
                    print(MATCHUP_WEEKLY_MODE_MESSAGE)
            else:
                print(MATCHUP_RANGE_NOT_FOUND_MESSAGE.format(matchup_links[0]))

        schedule, current_proxy = schedule_scraper.get_schedule(
            proxies,
            current_proxy,
            schedule_url=schedule_url_override,
            start_date=start_date,
            end_date=end_date,
        )

        filename = core_output.get_filename()
        workbook = xlsxwriter.Workbook(filename)
        matchups_worksheet = workbook.add_worksheet(name=MATCHUPS_WORKSHEET_NAME)

        roster_context = build_roster_context(workbook, matchups_context)

        current_proxy = roster_workflow.process_links(
            roster_context,
            team_links,
            proxies,
            choice,
            AVG_STATS_PAGE,
            matchup_links,
            schedule,
            matchups_worksheet,
            proxy=current_proxy,
        )

        workbook.close()
        core_output.open_file(filename)

    else:
        playoffs_in_progress = main_page_soup.find(string=re.compile(PLAYOFFS_HEADER))
        if playoffs_in_progress:
            team_links, current_proxy = get_links_from_standings(league_id, proxies, current_proxy)

        roster_context = build_roster_context(None, matchups_context)

        current_proxy = roster_workflow.process_links(
            roster_context,
            team_links,
            proxies,
            choice,
            RESEARCH_STATS_PAGE,
            proxy=current_proxy,
        )

        if choice == FORMAT_CHOICES["txt"]:
            core_output.open_file(TXT_FILENAME)
        elif choice == FORMAT_CHOICES["json"]:
            core_output.open_file(POSITIONS_FILENAME)


if __name__ == "__main__":
    main()
