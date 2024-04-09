import bs4
import json
import os
import num2words
import re
import sys
import subprocess
import datetime
import xlsxwriter

import proxies_scraper
import schedule_scraper
import positions_scraper


BASE_FANTASY_URL = 'https://hockey.fantasysports.yahoo.com/hockey/'
SEASON_IN_PROGRESS = True
SEASON_JUST_STARTED = False  # if stats are not representative enough yet, use stats from the last season

AVG_STATS_PAGE = {
    'stat1': 'AS',
}

if SEASON_JUST_STARTED:
    AVG_STATS_PAGE['stat2'] = 'AS_2022'  # Calculate year programmatically

if SEASON_IN_PROGRESS:
    START_FROM = 1
    NAME_COLUMN = 1
else:
    START_FROM = 1
    NAME_COLUMN = 0

PROXY_CHOICES = {'Y': True, 'n': False}
FORMAT_CHOICES = {'xlsx': '1', 'txt': '2', 'json': '3'}

PARSER = 'lxml'

NUMBER_OF_TEAMS_PROCESSED_MESSAGE = '{}/{} teams ready'
NUMBER_OF_MATCHUPS_PROCESSED_MESSAGE = '{}/{} matchups ready'
FORMAT_CHOICE_MESSAGE = ("Input 1 for full stats xls tables\n"
                         "Input 2 for simple txt rosters\n"
                         "Input 3 for positions in JSON file:\n")

PROXIES_CHOICE_MESSAGE = 'Use proxies? Y/n:\n'
INPUT_LEAGUE_ID_MESSAGE = "Input league's ID:\n"
INCORRECT_CHOICE_MESSAGE = 'Please select a correct option'
LEAGUE_ID_INCORRECT_MESSAGE = 'League with this ID does not exist or not publicly viewable'
LEAGUE_SCRAPING_SUCCESS_MESSAGE = "League's main page scraped!"

TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"
XLSX_FILENAME_TEMPLATE = 'reports/stats_list_{}.xlsx'
TXT_FILENAME = 'reports/clean_rosters.txt'
POSITIONS_FILENAME = 'reports/positions.json'
TEAM_NAME_HEADER = '--------------- {} ---------------'
MATCHUPS_WORKSHEET_NAME = 'MATCHUPS'

MATCHUP_CLASSES = 'Linkable Listitem No-p'
TEAMS_IN_MATCHUP_CLASSES = 'Fz-sm.Phone-fz-xs.Ell'
MATCHUP_RESULT_CLASSES = 'Table-plain Table Table-px-sm Table-mid Datatable Ta-center Tz-xxs Bdr'
TEAM_NAME_MATCHUP_RESULT_CLASSES = 'Grid-u Nowrap'
HEADERS_CLASSES = 'Alt Last'
TEAM_NAME_CLASSES = 'Navtarget F-reset No-case Fz-35 Fw-b team-name'
TEAM_NAME_STANDINGS_CLASSES = 'Grid-u F-reset Ell Mawpx-250'
PLAYOFFS_HEADER = 'Championship Bracket'
STANDINGS_PAGE_URL = 'https://hockey.fantasysports.yahoo.com/hockey/{}?module=standings&lhst=stand#lhststand'
EMPTY_SPOT_CLASSES = 'Nowrap emptyplayer Inlineblock'
SPOT_CLASS = 'pos-label'
PLAYER_NAME_CLASS = 'player'
PLAYER_LINK_CLASSES = 'Nowrap name F-link playernote'
TEAM_AND_POSITION_SPAN_CLASS = "Fz-xxs"

EMPTY_SPOT_STRING = 'Empty'
EMPTY_CELL = '-'

RESEARCH_STATS_PAGE = {
    'stat1': 'R',
}

OPPONENTS_PAGE = {
    'stat1': 'O',
}

INVALID_EXCEL_CHARACTERS_PATTERN = r"[*\\\/]"
EMPTY_STRING_PATTERN = r'^-$'

PLATFORMS = {
    'Windows': 'win32',
    'Mac_OS': 'darwin',
}

FILE_OPENERS = {'Linux': 'xdg-open', 'Mac_OS': 'open'}

POSITION_CODES = ['G', 'D', 'LW', 'RW', 'C']
NOT_PLAYING = ['IR', 'IR+', 'NA']
PRESEASON = 1
SEASON = 2

ROSTERED_COLUMN_INDEX = 7
WIDE_COLUMN_WIDTH = 20
NUMBER_OF_COLUMNS = 15
COLUMNS = {
    num2words.num2words(i + 1, to='ordinal'): (i, i)
    for i in range(NUMBER_OF_COLUMNS)
}

START_HEADERS = {'Spot': [], 'Forwards/Defensemen': [], 'Team': [], 'Pos': []}

SCORING_COLUMNS = [
    'G', 'A', '+/-', 'PIM', 'PPP', 'SHP', 'SOG', 'FW', 'HIT', 'BLK', 'GWG'
]
COLUMNS_TO_DELETE = [
    'Action', 'Add', 'Opp', 'Status', 'Pre-Season', 'Current', '% Started'
]

NHL_TEAM_NAMES_MAP = {
    'MON': 'MTL',
    'ANH': 'ANA',
    'NJ': 'NJD',
    'LA': 'LOS',
    'CLS': 'CBJ',
    'SJ': 'SJS',
    'TB': 'TBL',
    'WAS': 'WSH'
}



def scrape_from_page(soup, element_type, attr_type, attr_name):
    return soup.find_all(element_type, {attr_type: attr_name})


def get_team_name(soup):
    name_link = scrape_from_page(soup, 'span', 'class', re.compile(TEAM_NAME_CLASSES))[0]
    return name_link.text.strip()[:30]


def get_filename():
    now = datetime.datetime.now()
    timestamp = datetime.datetime.strftime(now, TIMESTAMP_FORMAT)
    filename = XLSX_FILENAME_TEMPLATE.format(timestamp)
    return filename


def open_file(filename):
    if sys.platform == PLATFORMS['Windows']:
        os.startfile(filename)
    else:
        if sys.platform == PLATFORMS['Mac_OS']:
            opener = FILE_OPENERS['Mac_OS']
        else:
            opener = FILE_OPENERS['Linux']

        subprocess.call([opener, filename])


def verify_sheet_name(team_name):
    return re.sub(INVALID_EXCEL_CHARACTERS_PATTERN, '', team_name)


def get_headers(soup):
    header_row = soup.find('tr', class_=HEADERS_CLASSES)
    headers = {**START_HEADERS, **{}}

    start_adding = False

    for child in header_row.children:
        name = child.string

        if SEASON_IN_PROGRESS:
            headers['Add'] = []

        if name == 'Action':
            start_adding = True

        if start_adding:
            headers[name] = []

    headers[schedule_scraper.GAMES_LEFT_THIS_WEEK_COLUMN] = []

    return headers


def get_body(soup, schedule):
    rows = soup.find('tbody').find_all('tr')
    cell_values = []

    for i, row in enumerate(rows):
        empty = row.find(class_=EMPTY_SPOT_CLASSES)
        index = 0

        if SEASON_IN_PROGRESS:
            spot = row.find(class_=SPOT_CLASS)

            if spot.string in NOT_PLAYING:
                continue

        for cell in row:
            if i == 0:
                cell_values.append([])

            if (PLAYER_NAME_CLASS in cell.attrs['class']):
                if i == 0:
                    cell_values.extend(([], []))

                player_link = cell.find(class_=PLAYER_LINK_CLASSES)
                if player_link:
                    name = player_link.string
                    span = cell.find(class_=TEAM_AND_POSITION_SPAN_CLASS)
                    team, position = span.string.split(' - ')

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
            try:
                cell_values[index].append(schedule[team.upper()][
                    schedule_scraper.GAMES_LEFT_THIS_WEEK_COLUMN])
            except KeyError:
                cell_values[index].append(
                    schedule[NHL_TEAM_NAMES_MAP[team.upper()]][
                        schedule_scraper.GAMES_LEFT_THIS_WEEK_COLUMN])

    return cell_values


def map_headers_to_body(headers, body):
    headers_keys = headers.copy().keys()
    games_per_week_column = body[-1]

    for index, key in enumerate(headers_keys):
        headers[key] = body[index]

        if (SEASON_IN_PROGRESS) and (key in SCORING_COLUMNS):
            headers[key].append(
                calculate_totals(headers[key], games_per_week_column))

        if key in COLUMNS_TO_DELETE:
            headers.pop(key, None)

    return headers


def calculate_totals(column_values, games_per_week):
    total = 0

    for index, value in enumerate(column_values):
        total += string_to_num(value, None) * games_per_week[index]

    return total


def string_to_num(value, delimeter):
    return float(re.sub(EMPTY_STRING_PATTERN, '0', value.split(delimeter)[0]))


def process_links(links, proxies, choice, stats_page, schedule=None):
    if proxies:
        proxy = proxies_scraper.get_proxy(proxies)

    json_dump_data = {}
    for index, link in enumerate(links):
        if proxies:
            web = proxies_scraper.get_response(link,
                                               stats_page,
                                               proxies=proxies,
                                               proxy=proxy)

            while not web:
                proxy = proxies_scraper.get_proxy(proxies)
                web = proxies_scraper.get_response(link,
                                                   stats_page,
                                                   proxies=proxies,
                                                   proxy=proxy)

        else:
            web = proxies_scraper.get_response(link, stats_page)

        soup = bs4.BeautifulSoup(web.text, PARSER)

        team_name = get_team_name(soup)

        if choice == FORMAT_CHOICES['xlsx']:
            headers = get_headers(soup)
            body = get_body(soup, schedule)
            table = map_headers_to_body(headers, body)
            sheet_name = verify_sheet_name(team_name)
            worksheet = workbook.add_worksheet(name=sheet_name)
            write_to_xlsx(table, worksheet)

        else:
            bodies = soup.find_all('tbody')

            if index == 0:
                file_mode = 'w'
            else:
                file_mode = 'a'

            if choice == FORMAT_CHOICES['txt']:
                data = parse_clean_names(bodies)
                write_roster_to_txt(data, file_mode, team_name)

            elif choice == FORMAT_CHOICES['json']:
                json_dump_data[team_name] = parse_for_json(bodies[0], team_name)

        print(NUMBER_OF_TEAMS_PROCESSED_MESSAGE.format(index+1, len(links)))

    if choice == FORMAT_CHOICES['json']:
        with open(POSITIONS_FILENAME, "w") as text_file:
            json.dump(json_dump_data, text_file, indent=2)


def parse_for_json(skaters, team_name):
    rows = skaters.find_all('tr')
    roster = []

    for row_index, row in enumerate(rows):
        for cell_index, cell in enumerate(row):
            if (PLAYER_NAME_CLASS in cell.attrs['class']):
                player_link = cell.find(class_=PLAYER_LINK_CLASSES)

                if player_link:
                    name = player_link.string
                    span = cell.find(class_=TEAM_AND_POSITION_SPAN_CLASS)
                    position = span.string.split(' - ')[1]
                    if position != POSITION_CODES[1]:
                        pos_data = positions_scraper.get_positional_data([],
                                                                         name)
                        roster.append(pos_data)
    return roster


def process_matchups(matchup_links, proxies):
    worksheet = workbook.add_worksheet(name=MATCHUPS_WORKSHEET_NAME)
    worksheet.set_column(*COLUMNS['first'], WIDE_COLUMN_WIDTH)
    headers = []
    worksheet_row_number = 0
    worksheet_rows = []
    worksheet_rows.append([])

    if proxies:
        proxy = proxies_scraper.get_proxy(proxies)
    else:
        proxy = None

    for link_index, link in enumerate(matchup_links):
        soup, proxy = parse_full_page(link, proxies, proxy)
        table = scrape_from_page(soup, 'table', 'class',
                                 MATCHUP_RESULT_CLASSES)[0]

        if not headers:
            headers = table.find('thead').find_all('th')

            for header in headers:
                worksheet_rows[worksheet_row_number].append(header.string)

            worksheet_row_number += 1
            worksheet_rows.append([])

        rows = table.find('tbody').find_all('tr')
        number_of_cells = 0

        for row in rows:
            cells = row.find_all('td')

            if not number_of_cells:
                number_of_cells = len(cells)

            for index, cell in enumerate(cells):
                try:
                    name = cell.find(
                        'span', class_=TEAM_NAME_MATCHUP_RESULT_CLASSES).string

                except AttributeError:
                    name = cell.string

                worksheet_rows[worksheet_row_number].append(name)

            worksheet_row_number += 1
            worksheet_rows.append([])

        print(
            NUMBER_OF_MATCHUPS_PROCESSED_MESSAGE.format(
                link_index + 1, len(matchup_links)))

        for cell in range(0, number_of_cells):
            worksheet_rows[worksheet_row_number].append(None)

        worksheet_row_number += 1
        worksheet_rows.append([])

    for index, row in enumerate(worksheet_rows):
        worksheet.write_row(index, 0, row)


def parse_full_page(link, proxies, proxy=None, params={}):
    if proxies:
        if not proxy:
            proxy = proxies_scraper.get_proxy(proxies)

        web = proxies_scraper.get_response(link,
                                           params,
                                           proxies=proxies,
                                           proxy=proxy)

        while not web:
            proxy = proxies_scraper.get_proxy(proxies)
            web = proxies_scraper.get_response(link,
                                               params,
                                               proxies=proxies,
                                               proxy=proxy)

    else:
        web = proxies_scraper.get_response(link, params)

    return (bs4.BeautifulSoup(web.text, PARSER), proxy)


def parse_clean_names(bodies):
    full_roster = []
    for body in bodies:
        rows = body.find_all('tr')

        txt = []
        for row_index, row in enumerate(rows):
            for cell_index, cell in enumerate(row):
                if (PLAYER_NAME_CLASS in cell.attrs['class']):
                    player_link = cell.find(class_=PLAYER_LINK_CLASSES)
                    txt.append([])

                    if player_link:
                        name = player_link.string
                        txt[row_index].append(name)

                    else:
                        txt[row_index].append(EMPTY_SPOT_STRING)

                if cell_index == ROSTERED_COLUMN_INDEX:
                    txt[row_index].append(cell.string)

        # Rostered % strings converted to float and sorted
        res = sorted(txt, key=lambda x: string_to_num(x[1], '%'), reverse=True)
        zipped = list(zip(*res))
        full_roster.append(zipped[0])

    return full_roster


def write_roster_to_txt(full_roster, file_mode, team_name):
    with open(TXT_FILENAME, file_mode) as text_file:
        text_file.write(TEAM_NAME_HEADER.format(team_name))
        text_file.write('\n\n')

        for roster in full_roster:
            text_file.write("\n".join(
                str(item) for item in roster if item != EMPTY_SPOT_STRING))
            text_file.write('\n\n')

        text_file.write('\n')


def validate_input(message, choices):
    choice = input(message)

    if choice in choices:
        return choice
    else:
        print(INCORRECT_CHOICE_MESSAGE)
        return None


def get_links(soup):
    matchups = scrape_from_page(soup, 'li', 'class', MATCHUP_CLASSES)

    if matchups:
        matchup_links = []
        team_links = []

        for match in matchups:
            matchup_links.append(
                f"{link}/{match.attrs['data-target'].split('/')[-1]}")
            teams = match.select(f"div.{TEAMS_IN_MATCHUP_CLASSES}")

            for team in teams:
                html_link = team.find('a')
                base_team_url = html_link.get('href')
                team_links.append(base_team_url)

        print(LEAGUE_SCRAPING_SUCCESS_MESSAGE)
        return (matchup_links, team_links)

    else:
        print(LEAGUE_ID_INCORRECT_MESSAGE)
        return None


def write_to_xlsx(table, worksheet):
    col_num = 0
    worksheet.set_column(*COLUMNS['second'], WIDE_COLUMN_WIDTH)

    for key, value in table.items():
        worksheet.write(0, col_num, key)
        worksheet.write_column(1, col_num, value)
        col_num += 1


def get_links_from_standings(league_id):
    standings_page_soup = parse_full_page(STANDINGS_PAGE_URL.format(league_id), proxies)[0]
    teams = scrape_from_page(standings_page_soup, 'a', 'class', TEAM_NAME_STANDINGS_CLASSES)
    return [team_link.get('href') for team_link in teams]


if __name__ == '__main__':
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
    main_page_soup = parse_full_page(link, proxies)[0]
    league_scrapable = get_links(main_page_soup)

    while not league_scrapable:
        league_id = input(INPUT_LEAGUE_ID_MESSAGE)
        link = BASE_FANTASY_URL + league_id
        main_page_soup = parse_full_page(link, proxies)[0]
        league_scrapable = get_links(main_page_soup)

    team_links = league_scrapable[1]

    choice = validate_input(FORMAT_CHOICE_MESSAGE, FORMAT_CHOICES.values())
    while not choice:
        choice = validate_input(FORMAT_CHOICE_MESSAGE, FORMAT_CHOICES.values())

    if choice == FORMAT_CHOICES['xlsx']:
        schedule = schedule_scraper.get_schedule(proxies)
        matchup_links = league_scrapable[0]

        filename = get_filename()
        workbook = xlsxwriter.Workbook(filename)

        process_matchups(matchup_links, proxies)
        process_links(team_links, proxies, choice, AVG_STATS_PAGE, schedule)

        workbook.close()
        open_file(filename)

    else:
        playoffs_in_progress = main_page_soup.find(string=re.compile(PLAYOFFS_HEADER))
        if playoffs_in_progress:
            team_links = get_links_from_standings(league_id)

        process_links(team_links, proxies, choice, RESEARCH_STATS_PAGE)

        if choice == FORMAT_CHOICES['txt']:
            open_file(TXT_FILENAME)
        elif choice == FORMAT_CHOICES['json']:
            open_file(POSITIONS_FILENAME)
