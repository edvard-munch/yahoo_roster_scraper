from lxml import etree
import requests
import bs4
import time
import os
import re
import sys
import subprocess
import xlsxwriter

import proxies_scraper

# BASE_FANTASY_URL = 'https://hockey.fantasysports.yahoo.com'
PARSER = 'lxml'
EMPTY_CELL = '-'

SEASON_IN_PROGRESS = True
SEASON_JUST_STARTED = False

AVG_STATS_PAGE = {
    'stat1': 'AS',
    # 'ssort': 'D', needed for off-season????
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
def open_file(filename):
    if sys.platform == PLATFORMS['Windows']:
        os.startfile(filename)
    else:
        if sys.platform == PLATFORMS['Mac_OS']:
            opener = FILE_OPENERS['Mac_OS']
        else:
            opener = FILE_OPENERS['Linux']

def write_to_xlsx(table):
    team_name = get_team_name(soup)
    sheet_name = verify_sheet_name(team_name)
    worksheet = workbook.add_worksheet(name=sheet_name)
        subprocess.call([opener, filename])

    print(f'{sheet_name} written!')

    col_num = 0
    for key, value in table.items():
        worksheet.write(0, col_num, key)
        worksheet.write_column(1, col_num, value)
        col_num += 1
# def get_rosters_in_txt(names, file_mode, team_name):
#     print(names)
#     with open("reports/clean_rosters.txt", file_mode) as text_file:
#         text_file.write(f'---------------{team_name}---------------')
#         text_file.write('\n\n')
#         text_file.write("\n".join(str(item) for item in names[1]))
#         text_file.write('\n\n')
#         text_file.write("\n".join(str(item) for item in names[0]))
#         text_file.write('\n\n\n')


def get_response(link, proxy, proxies):
    print(f"Trying with IP: {proxy['http']}")

    if proxy:
        try:
            web = requests.get(link, params=AVG_STATS_PAGE,
                               proxies=proxy, timeout=REQUEST_TIMEOUT)
            print(web.url)
            return web

        except (requests.ConnectTimeout, OSError) as e:
            print('Connnection Error. Retry')
            proxies.remove(proxy)
            print(f'Proxies left: {len(proxies)}')
    else:
        web = requests.get(link, params=AVG_STATS_PAGE)
        return web

    filename = get_filename()
    workbook = xlsxwriter.Workbook(filename)

def process_links(links, proxies):
    counter = 0
    fnh = False

    proxy = proxies_scraper.get_proxy(proxies)

    for index, link in enumerate(links):
        if FNH_LEAGUE_CODE in link:
            fnh = True

        web = get_response(link, proxy, proxies)

        while not web:
            proxy = proxies_scraper.get_proxy(proxies)
            web = get_response(link, proxy, proxies)

        if index == 0:
            file_mode = 'w'
        else:
            file_mode = 'a'

        soup = bs4.BeautifulSoup(web.text, PARSER)
        skaters_table = scrape_from_page(web, 'div', 'id', 'statTable0-wrap')[0]
        # goalies_table = scrape_from_page(web, 'div', 'id', 'statTable1-wrap')

        write_to_xlsx(table)



        team_name = get_team_name(web)
        # get_rosters_in_txt(get_full_table(web, skaters_table)[1], file_mode,
        #                    team_name)

        sheet_name = verify_sheet_name(team_name)
        print(sheet_name)
        add_to_sheet(writer, players_df, sheet_name)
        print('SHEET ADDED')

        counter += 1
        print(f'Teams added: {counter}')


def verify_sheet_name(team_name):
    return re.sub(INVALID_EXCEL_CHARACTERS_PATTERN, '', team_name)



def get_links(link):
    web = requests.get(link)
    team_links = []
    matchs = scrape_from_page(web, 'div', 'class', 'Grid-table Phone-px-med')

    counter = 0
    for match in matchs:
        teams = match.find_all('div', {'class': 'Fz-sm Phone-fz-xs Ell Mawpx-150'})
        counter += 1

        for team in teams:
            html_link = team.find('a')
            base_team_url = html_link.get('href')
            team_links.append(base_team_url)

    return team_links


if __name__ == '__main__':
    # web = get_response(SCHEDULE_URL)
    # soup = bs(web.content, 'html.parser')
    # # suffix = 0
    # # while suffix < 3:
    # # res = scrape_from_page(web, 'table', 'id', 'table_id')
    # # print(type(res))
    # new = soup.find_all('tr', class_="odd")
    # # new = soup.find_all("tr", limit=2)
    # print(new)
    # return bs(web.text, 'lxml').find_all(element_type, {attr_type: attr_name})
    # div class="article__rte"

    league_link = 'https://hockey.fantasysports.yahoo.com/hockey/6479'

    links = [
        'https://hockey.fantasysports.yahoo.com/hockey/6479/8',
        # 'https://hockey.fantasysports.yahoo.com/hockey/6479/1',
    ]

    links = get_links(league_link)

    for link in links:
        print(link)
    proxies = proxies_scraper.get_proxies()
    proxies = proxies_scraper.scrape_proxies()

    print(proxies)

    filename = get_filename()
    process_links(links, proxies)


    open_file(filename)
    # open_file("reports/clean_rosters.txt")
