import datetime
import re
from urllib.parse import urljoin

import bs4
import num2words

from . import proxies as proxies_scraper
from . import schedule as schedule_scraper
from roster_scraper.core import parsing as core_parsing

BASE_FANTASY_URL = "https://hockey.fantasysports.yahoo.com/hockey/"
FORMAT_CHOICES = {"xlsx": "1", "txt": "2", "json": "3", "google_sheets": "4"}
PARSER = "lxml"
NUMBER_OF_TEAMS_PROCESSED_MESSAGE = "{}/{} teams ready"
NUMBER_OF_MATCHUPS_PROCESSED_MESSAGE = "{}/{} matchups ready"
LEAGUE_ID_INCORRECT_MESSAGE = "League with this ID does not exist or not publicly viewable"
NO_MATCHUPS_FOUND_MESSAGE = "No matchups found (preseason/off-season); continuing with team links."
LEAGUE_SCRAPING_SUCCESS_MESSAGE = "League's main page scraped!"
POSITIONS_FILENAME = "reports/positions.json"
MATCHUP_CLASSES = "Linkable Listitem No-p"
TEAMS_IN_MATCHUP_CLASSES = "Fz-sm.Phone-fz-xs.Ell"
MATCHUP_RESULT_CLASSES = "Table-plain Table Table-px-sm Table-mid Datatable Ta-center Tz-xxs Bdr"
TEAM_NAME_MATCHUP_RESULT_CLASSES = "Grid-u Nowrap"
HEADERS_CLASSES = "Alt Last"
TEAM_NAME_CLASSES = "Navtarget No-pbot F-reset No-case Fz-35 Fw-b team-name"
TEAM_NAME_STANDINGS_CLASSES = "Grid-u F-reset Ell Mawpx-250"
TEAM_ROW_CLASSES = "Listitem No-p"
TEAM_NAME_LINK_CLASSES = "F-link"
TEAM_LINK_TEAM_ID_PATTERN = re.compile(r"/hockey/(?:\d+/)?(?P<team_id>\d+)$")
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
SPACER_CLASS = "Spacer"
SPOT_CLASS = "pos-label"
PLAYER_NAME_CLASS = "player"
PLAYER_LINK_CLASSES = re.compile(r"Nowrap\s+name\s+F-link(?:\s+\S+)?", re.IGNORECASE)
TEAM_AND_POSITION_SPAN_CLASS = "Fz-xxs"
MATCHUP_TOTALS_PARAMETER = "&date=total"
MATCHUP_RANGE_DAYS_THRESHOLD = 7
EMPTY_SPOT_STRING = "Empty"
EMPTY_CELL = "-"
RESEARCH_STATS_PAGE = {
    "stat1": "R",
}
NOT_PLAYING = ["IR", "IR+", "NA"]
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


def get_roster_header_row(soup):
    header_row = soup.find("tr", class_=HEADERS_CLASSES)

    if not header_row:
        for row in soup.find_all("tr"):
            header_names = [cell.get_text(strip=True) for cell in row.find_all(["th", "td"])]
            if "Action" in header_names:
                header_row = row
                break

    return header_row


def is_spacer_cell(cell):
    class_names = cell.get("class") or []
    return SPACER_CLASS in class_names


def get_headers(soup, *, season_in_progress):
    header_row = get_roster_header_row(soup)

    if not header_row:
        raise RuntimeError("Roster header row not found")

    headers = {**START_HEADERS, **{}}

    start_adding = False

    for child in header_row.find_all(["th", "td"]):
        if is_spacer_cell(child):
            continue

        name = child.get_text(strip=True)

        if season_in_progress:
            headers["Add"] = []

        if name == "Action":
            start_adding = True

        if start_adding:
            headers[name] = []

    headers[schedule_scraper.GAMES_LEFT_THIS_WEEK_COLUMN] = []

    return headers


def get_body(soup, schedule, missing_schedule_teams=None, *, season_in_progress):
    header_row = get_roster_header_row(soup)

    if header_row:
        roster_table = header_row.find_parent("table")
        skater_rows = roster_table.find("tbody").find_all("tr")
    else:
        skater_rows = soup.find_all("tbody")[1].find_all("tr")

    cell_values = []

    for i, row in enumerate(skater_rows):
        empty = row.find(class_=EMPTY_SPOT_CLASSES)
        index = 0

        if season_in_progress:
            spot = row.find(class_=SPOT_CLASS)

            if spot.string in NOT_PLAYING:
                continue

        for cell in row:
            if is_spacer_cell(cell):
                continue

            if i == 0:
                cell_values.append([])

            if PLAYER_NAME_CLASS in cell.attrs["class"]:
                if i == 0:
                    cell_values.extend(([], []))
                player_link = cell.find(
                    lambda tag: (
                        tag.get("class") and PLAYER_LINK_CLASSES.search(" ".join(tag.get("class")))
                    )
                )
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


def build_avg_stats_page(season_just_started):
    avg_stats_page = {"stat1": "AS"}

    if season_just_started:
        avg_stats_page["stat2"] = "AS_2025"  # Calculate year programmatically

    return avg_stats_page


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

    return ([], [])


def get_team_links_from_league(soup, league_link):
    team_links = []
    team_rows = scrape_from_page(soup, "li", "class", re.compile(TEAM_ROW_CLASSES))

    for row in team_rows:
        team_link = row.find("a", class_=TEAM_NAME_LINK_CLASSES)

        if team_link and team_link.get("href"):
            team_name = team_link.get_text(strip=True)
            team_links.append((urljoin(league_link, team_link["href"]), team_name))

    return team_links


def get_links_from_standings(league_id, proxies, proxy=None):
    standings_page_soup, proxy = parse_full_page(
        STANDINGS_PAGE_URL.format(league_id), proxies, proxy
    )
    teams = scrape_from_page(standings_page_soup, "a", "class", TEAM_NAME_STANDINGS_CLASSES)
    return [team_link.get("href") for team_link in teams], proxy


def inspect_team_link(team_link, proxies, proxy=None):
    try:
        soup, proxy = parse_full_page(team_link, proxies, proxy)
    except RuntimeError:
        return None, proxy

    bodies = soup.find_all("tbody")
    roster_groups = core_parsing.parse_clean_names(bodies[1:])
    has_players = any(
        player and player != EMPTY_SPOT_STRING for group in roster_groups for player in group
    )

    if not has_players:
        return None, proxy

    return get_team_name(soup), proxy


def extract_team_id(team_link):
    match = TEAM_LINK_TEAM_ID_PATTERN.search(team_link or "")
    return match.group("team_id") if match else None


def merge_team_links(preferred_links, extra_links):
    merged = []
    seen_names = set()
    seen_team_ids = set()

    for link, team_name in [*preferred_links, *extra_links]:
        team_id = extract_team_id(link)

        if team_name and team_name in seen_names:
            continue

        if not team_name and team_id and team_id in seen_team_ids:
            continue

        if team_name:
            seen_names.add(team_name)
        elif team_id:
            seen_team_ids.add(team_id)

        if team_id:
            seen_team_ids.add(team_id)

        merged.append(link)

    return merged


def resolve_league_links(
    main_page_soup,
    league_link,
    league_id,
    season_mode,
    proxies,
    proxy=None,
):
    matchup_links, team_links = get_links(main_page_soup, league_link)

    if matchup_links:
        return (matchup_links, team_links), proxy

    if season_mode.in_progress:
        print(LEAGUE_ID_INCORRECT_MESSAGE)
        return None, proxy

    league_page_team_links = get_team_links_from_league(main_page_soup, league_link)
    standings_team_links, proxy = get_links_from_standings(league_id, proxies, proxy)
    extra_team_links = []

    for link in standings_team_links:
        team_name, proxy = inspect_team_link(link, proxies, proxy)

        if not team_name:
            continue

        extra_team_links.append((link, team_name))

    team_links = merge_team_links(league_page_team_links, extra_team_links)

    if team_links:
        print(NO_MATCHUPS_FOUND_MESSAGE)
        return ([], team_links), proxy

    print(LEAGUE_ID_INCORRECT_MESSAGE)
    return None, proxy


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
