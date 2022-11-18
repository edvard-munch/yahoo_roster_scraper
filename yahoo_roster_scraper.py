import requests
import bs4
import os
import re
import sys
import subprocess
import time
import xlsxwriter

import proxies_scraper


# check +- SUM calculations

LEAGUE_LINK = 'https://hockey.fantasysports.yahoo.com/hockey/9197'
SEASON_IN_PROGRESS = True
SEASON_JUST_STARTED = False

USE_PROXIES = True
REQUEST_TIMEOUT = 1

CHOICES = {'xlsx': '1', 'txt': '2'}

CONNECTION_ERROR_MESSAGE = 'Connnection Error. Retry'
PROXIE_CONNECTION_ATTEMPT_MESSAGE = 'Trying with IP: {}'
PROXIES_LEFT_MESSAGE = 'Proxies left: {}'
NUMBER_OF_TEAMS_PROCESSED_MESSAGE = '{}/{} teams ready'
CHOICE_MESSAGE = 'Input 1 for full stats xls tables, input 2 for simple txt rosters:\n'
INCORRECT_CHOICE_MESSAGE = 'Please select a correct option'

PARSER = 'lxml'
EMPTY_CELL = '-'

TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"
XLSX_FILENAME_TEMPLATE = 'reports/stats_list_{}.xlsx'
TXT_FILENAME = 'reports/clean_rosters.txt'
TEAM_NAME_HEADER = '--------------- {} ---------------'

MATCHUPS_CLASSES = 'Grid-table Phone-px-med'
TEAMS_IN_MATCHUP_CLASSES = 'Fz-sm Phone-fz-xs Ell Mawpx-150'
HEADERS_CLASSES = 'Alt Last'
TEAM_NAME_CLASSES = 'Navtarget Py-sm Pstart-lg F-reset Wordwrap-bw No-case'
EMPTY_SPOT_CLASSES = 'Nowrap emptyplayer Inlineblock'
SPOT_CLASS = 'pos-label'
PLAYER_NAME_CLASS = 'player'
PLAYER_LINK_CLASSES = 'Nowrap name F-link'
TEAM_AND_POSITION_SPAN_CLASS = "Fz-xxs"

EMPTY_SPOT_STRING = 'Empty'

AVG_STATS_PAGE = {
    'stat1': 'AS',
}

RESEARCH_STATS_PAGE = {
    'stat1': 'R',
}

# if stats are not representative enough yet, use stats from the last season
if SEASON_JUST_STARTED:
    AVG_STATS_PAGE['stat2'] = 'AS_2021'

FNH_LEAGUE_CODE = '9197'

INVALID_EXCEL_CHARACTERS_PATTERN = r"[*\\\/]"

OPPONENTS_PAGE = {
    'stat1': 'O',
}

PLATFORMS = {
    'Windows': 'win32',
    'Mac_OS': 'darwin',
}

FILE_OPENERS = {
    'Linux': 'xdg-open',
    'Mac_OS': 'open'
}

NOT_PLAYING = ['IR', 'IR+', 'NA']
PRESEASON = 1
SEASON = 2

ROSTERED_COLUMN_INDEX = 7
REQUEST_TIMEOUT = 7

if SEASON_IN_PROGRESS:
    START_FROM = 1
    NAME_COLUMN = 1
else:
    START_FROM = 1
    NAME_COLUMN = 0

START_HEADERS = {
    'Spot': [], 'Forwards/Defensemen': [], 'Team': [], 'Pos': []
}

SCORING_COLUMNS = ['G', 'A', '+/-', 'PIM', 'PPP', 'SHP', 'SOG', 'FW', 'HIT', 'BLK']

COLUMNS_TO_DELETE = ['Action', 'Add', 'Opp', 'Status', 'Pre-Season', 'Current',
                     '% Started']

# Seems like it's not scrapable
SCHEDULE_URL = 'https://leftwinglock.com/schedules'


def scrape_from_page(soup, element_type, attr_type, attr_name):
    return soup.find_all(element_type, {attr_type: attr_name})


def get_team_name(soup):
    attr_name = 'Navtarget Py-sm Pstart-lg F-reset Wordwrap-bw No-case'
    name_link = scrape_from_page(soup, 'a', 'class', attr_name)[0]
    return name_link.text.split('  ')[0]


def get_filename():
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"reports/stats_list_{timestamp}.xlsx"
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


def get_links(link):
    web = requests.get(link)
    soup = bs4.BeautifulSoup(web.text, PARSER)
    team_links = []
    matchs = scrape_from_page(soup, 'div', 'class', 'Grid-table Phone-px-med')

    for match in matchs:
        teams = match.find_all('div', {'class': 'Fz-sm Phone-fz-xs Ell Mawpx-150'})

        for team in teams:
            html_link = team.find('a')
            base_team_url = html_link.get('href')
            team_links.append(base_team_url)

    return team_links


def get_headers(soup):
    header_row = soup.find('tr', class_='Alt Last')
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

    return headers


def get_full_table(soup, headers):
    rows = soup.find('tbody').find_all('tr')
    cell_values = []

    for i, row in enumerate(rows):
        empty = row.find(class_='Nowrap emptyplayer Inlineblock')
        index = 0
        for cell in row:
            if i == 0:
                cell_values.append([])

            if ('player' in cell.attrs['class']):
                if i == 0:
                    cell_values.extend(([],[]))

                player_link = cell.find(class_ = 'Nowrap name F-link')
                if player_link:
                    name = player_link.string
                    span = cell.find(class_ = "Fz-xxs")
                    team, position = span.string.split(' - ')

                    cell_values[index].append(name)
                    cell_values[index+1].append(team)
                    cell_values[index+2].append(position)
                    index += 3
                else:
                    cell_values[index].append(EMPTY_CELL)
                    cell_values[index+1].append(EMPTY_CELL)
                    cell_values[index+2].append(EMPTY_CELL)
                    index += 3    

            else:
                if (index > 0) and empty:
                    cell_values[index].append(EMPTY_CELL)

                else:  
                    cell_values[index].append(cell.string)

                index += 1        

    # map_ list_ of lists to dict_ of lists
    ind = 0
    for key in headers.copy().keys():
        headers[key] = cell_values[ind]
def get_filename():
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"reports/stats_list_{timestamp}.xlsx"
    return filename

        if key in SCORING_COLUMNS:
            # hacky line for computing totals of avg stats
            headers[key].append(sum([float(val.replace(EMPTY_CELL, '0')) for val in headers[key]]))

        if key in COLUMNS_TO_DELETE:
            headers.pop(key, None)
        
        ind += 1

    # add_totals(headers, False)

    return headers


def string_to_num(value, delimeter):
    return float(value.split(delimeter)[0].replace(EMPTY_CELL, '0'))


def write_to_xlsx(table, team_name):
    sheet_name = verify_sheet_name(team_name)
    worksheet = workbook.add_worksheet(name=sheet_name)

    col_num = 0
    for key, value in table.items():
        worksheet.write(0, col_num, key)
        worksheet.write_column(1, col_num, value)
        col_num += 1


def get_response(link, stats_page, **proxie_data):
    if proxie_data:
        print(PROXIE_CONNECTION_ATTEMPT_MESSAGE.format(proxie_data['proxy']['http']))

        try:
            web = requests.get(link, params=stats_page,
                               proxies=proxie_data['proxy'], timeout=REQUEST_TIMEOUT)

        except (requests.ConnectTimeout, OSError) as e:
            print(CONNECTION_ERROR_MESSAGE)
            proxie_data['proxies'].remove(proxie_data['proxy'])
            print(PROXIES_LEFT_MESSAGE.format(len(proxie_data["proxies"])))
            return None
    else:
        web = requests.get(link, params=stats_page)

    return web


def process_links(links, use_proxies, choice, stats_page):

    if use_proxies:
        proxies = proxies_scraper.scrape_proxies()
        proxy = proxies_scraper.get_proxy(proxies)

    for index, link in enumerate(links):

        if use_proxies:
            web = get_response(link, stats_page,  proxies=proxies, proxy=proxy)

            while not web:
                proxy = proxies_scraper.get_proxy(proxies)
                web = get_response(link, stats_page, proxies=proxies, proxy=proxy)

        else:
            web = get_response(link, stats_page)

        soup = bs4.BeautifulSoup(web.text, PARSER)

        team_name = get_team_name(soup)

        if choice == CHOICES['xlsx']:
            headers = get_headers(soup)
            body = get_body(soup)
            table = map_headers_to_body(headers, body)
            write_to_xlsx(table, team_name)

        elif choice == CHOICES['txt']:
            bodies = soup.find_all('tbody')
            parse_clean_names(bodies)

            if index == 0:
                file_mode = 'w'
            else:
                file_mode = 'a'

            write_roster_to_txt(parse_clean_names(bodies), file_mode, team_name)

        print(NUMBER_OF_TEAMS_PROCESSED_MESSAGE.format(index+1, len(links)))


def parse_clean_names(bodies):
    full_roster = []

    for body in bodies:
        rows = body.find_all('tr')

        txt = []

        for row_index, row in enumerate(rows):
            for cell_index, cell in enumerate(row):
                if (PLAYER_NAME_CLASS in cell.attrs['class']):
                    player_link = cell.find(class_ = PLAYER_LINK_CLASSES)
                    txt.append([])

                    if player_link:
                        name = player_link.string
                        txt[row_index].append(name)
                    else:
                        txt[row_index].append(EMPTY_SPOT_STRING)

                if cell_index == ROSTERED_COLUMN_INDEX:
                    txt[row_index].append(cell.string)

        # '25%' kind of strings converted to float and sorted
        res = sorted(txt, key=lambda x: string_to_num(x[1], '%'), reverse=True)
        zipped = list(zip(*res))
        full_roster.append(zipped[0])

    return full_roster


def write_roster_to_txt(full_roster, file_mode, team_name):
    with open(TXT_FILENAME, file_mode) as text_file:
        text_file.write(TEAM_NAME_HEADER.format(team_name))
        text_file.write('\n\n')

        for roster in full_roster:
            text_file.write("\n".join(str(item) for item in roster if item != EMPTY_SPOT_STRING))
            text_file.write('\n\n')

        text_file.write('\n')


def request_input():
    choice = input(CHOICE_MESSAGE)

    if choice in CHOICES.values():
        return choice
    else:
        print(INCORRECT_CHOICE_MESSAGE)
        return None


if __name__ == '__main__':
    links = get_links(LEAGUE_LINK)

    choice = request_input()

    while not choice:
        choice = request_input()

    if choice == CHOICES['xlsx']:
        filename = get_filename()
        workbook = xlsxwriter.Workbook(filename)

        process_links(links, USE_PROXIES, choice, AVG_STATS_PAGE)

        workbook.close()
        open_file(filename)

    elif choice == CHOICES['txt']:
        process_links(links, USE_PROXIES, choice, RESEARCH_STATS_PAGE)
        open_file(TXT_FILENAME)
