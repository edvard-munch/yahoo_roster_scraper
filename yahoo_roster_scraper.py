import pandas as pd
import lxml.html as lh
from lxml import etree
import requests
from bs4 import BeautifulSoup as bs
import time
import os
import random
import re
import sys
import subprocess

import proxies_scraper

# BASE_FANTASY_URL = 'https://hockey.fantasysports.yahoo.com'

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

if SEASON_IN_PROGRESS:
    START_FROM = 1
    NAME_COLUMN = 1
else:
    START_FROM = 1
    NAME_COLUMN = 0

COLUMNS_TO_DELETE = ['Action', 'Add', 'Opp', 'Status', 'Pre-Season', 'Current',
                     '% Started']

# Seems like it's not scrapable
SCHEDULE_URL = 'https://leftwinglock.com/schedules'


def find_tr_elements(web):
    doc = lh.fromstring(web.content)
    return doc.xpath('//tr')[START_FROM:]


# all find instead of find_all
def scrape_from_page(web, element_type, attr_type, attr_name):
    return bs(web.text, 'lxml').find_all(element_type, {attr_type: attr_name})


def get_team_name(web):
    attr_name = 'Navtarget Py-sm Pstart-lg F-reset Wordwrap-bw No-case'
    name_link = scrape_from_page(web, 'a', 'class', attr_name)[0]
    return name_link.text.split('  ')[0]


def get_clean_names(table):
    clean_names = []

    for link in table.findAll(attrs={"class": "Nowrap name F-link"}):
        clean_names.append(link.string)

    return clean_names


def get_clean_teams_and_positions(table):
    clean_teams = []
    clean_positions = []
    spans = table.findAll(attrs={"class": "Fz-xxs"})
    for index, span in enumerate(spans):

        try:
            team, position = span.string.split(' - ')
        except (AttributeError, ValueError):
            continue

        clean_teams.append(team)
        clean_positions.append(position)

    return (clean_teams, clean_positions)


def get_headers(web):
    tr_headers = find_tr_elements(web)[0]

    headers = []

    for header in tr_headers:
        name = header.text_content()

        if not name:
            pass
        else:
            headers.append((name, []))

        if SEASON_IN_PROGRESS and name == 'Opp':
            headers.append(("Add", []))

    return headers


def get_full_table(web, *skaters_table):
    table = get_headers(web)
    tr_rows = find_tr_elements(web)[1:]
    clean_names = get_clean_names(skaters_table[0])
    clean_teams, clean_positions = get_clean_teams_and_positions(skaters_table[0])

    goalies = {}
    skaters = {}
    dict_to_add = skaters

    for row_index, row in enumerate(tr_rows):

        slot_is_empty = False
        # row = tr_rows[row_index]    # WHAAAT?

        # for txt rosters
        row_content = str(etree.tostring(row, pretty_print=True))

        if 'Goaltenders' in row_content:
            dict_to_add = goalies

        for a in row.iter('a'):
            if a.get('class') == 'Nowrap name F-link':
                name_ = a.text

        for td in row.iter('td'):
            if td.get('class') == "Alt Ta-end Nowrap Bdrend":
                started_percent = td.find('div').text
                dict_to_add[name_] = started_percent

        try:
            name = clean_names[row_index]

            for cell_index, cell in enumerate(row.iterchildren()):
                data = cell.text_content()

                if table[cell_index][0] == 'Forwards/Defensemen':
                    if 'Empty' in data:
                        slot_is_empty = True
                        clean_names.insert(row_index, '-')
                        clean_teams.insert(row_index, '-')
                        clean_positions.insert(row_index, '-')
                        table[cell_index][1].append('(Empty)')

                    else:
                        table[cell_index][1].append(name)

                else:
                    if slot_is_empty:
                        table[cell_index][1].append('-')
                    else:
                        table[cell_index][1].append(data)

        # check why break didn't work
        except IndexError:
            pass

    sorted_names = (
        sorted(goalies, key=lambda x: float(goalies[x][:-1]), reverse=True),
        sorted(skaters, key=lambda x: float(skaters[x][:-1]), reverse=True)
    )

    table.insert(3, ('Team', clean_teams))
    table.insert(4, ('Position', clean_positions))

    # print(sorted_names)
    return table, sorted_names


def get_dataframe_from_list(web, skaters_table):
    players_dict = {title: column for (title, column) in get_full_table(web, skaters_table)[0]}
    
    # DEBUGGING
    # for key, value in players_dict.items():
    #     print(f'Length of {key}: {len(value)}')

    return pd.DataFrame(players_dict)


def delete_columns(players_df):
    del_columns = COLUMNS_TO_DELETE

    if not SEASON_IN_PROGRESS:
        del_columns.remove('Add')

    if 'TOI/G*' in players_df.columns:
        del_columns.append('TOI/G*')

    if 'GP*' in players_df.columns:
        del_columns.append('GP*')

    players_df.drop(del_columns, axis=1, inplace=True)

    if SEASON_IN_PROGRESS:
        for index, player in players_df.iterrows():
            if player['Spot'] in NOT_PLAYING:
                players_df.drop([index], inplace=True)

    return players_df


def add_total_row(players_df, fnh):
    cols = ['G', 'A', '+/-', 'PIM', 'PPP', 'SHP', 'SOG', 'FW', 'HIT', 'BLK']

    if fnh:
        cols.insert(5, 'GWG')

    players_df[cols] = players_df[cols].apply(pd.to_numeric, errors='coerce',
                                              axis=1)
    players_df.loc["Total"] = players_df.select_dtypes(exclude=['object']).sum()


def get_filename():
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"reports/stats_list_{timestamp}.xlsx"
    return filename


def add_to_sheet(writer, players_df, sheet_name):
    players_df.to_excel(writer, sheet_name=sheet_name, index=False)
    writer.sheets[sheet_name].set_column(NAME_COLUMN, NAME_COLUMN, 23)


def open_file(filename):
    if sys.platform == PLATFORMS['Windows']:
        os.startfile(filename)
    else:
        if sys.platform == PLATFORMS['Mac_OS']:
            opener = FILE_OPENERS['Mac_OS']
        else:
            opener = FILE_OPENERS['Linux']

        subprocess.call([opener, filename])


# def get_rosters_in_txt(names, file_mode, team_name):
#     print(names)
#     with open("reports/clean_rosters.txt", file_mode) as text_file:
#         text_file.write(f'---------------{team_name}---------------')
#         text_file.write('\n\n')
#         text_file.write("\n".join(str(item) for item in names[1]))
#         text_file.write('\n\n')
#         text_file.write("\n".join(str(item) for item in names[0]))
#         text_file.write('\n\n\n')


def get_proxy(ip_addresses):

    if ip_addresses:
        proxy_index = random.randint(0, len(ip_addresses) - 1)
        return ip_addresses[proxy_index]

    else:
        print('No free proxies available. Refresh proxies list and try again!')
        sys.exit(1)


def get_response(link, ip_addresses):
    proxy = get_proxy(ip_addresses)
    print(f"Trying with IP: {proxy['http']}")

    if proxy:
        try:
            web = requests.get(link, params=AVG_STATS_PAGE,
                               proxies=proxy, timeout=7)
            print(web.url)
            return web

        except (requests.ConnectTimeout, OSError) as e:
            print('Connnection Error. Retry')
            ip_addresses.remove(proxy)
            print(f'Proxies left: {len(ip_addresses)}')
    else:
        web = requests.get(link, params=AVG_STATS_PAGE)
        return web


def process_links(links, ip_addresses):
    counter = 0
    fnh = False

    proxy = get_proxy(ip_addresses)

    for index, link in enumerate(links):
        if FNH_LEAGUE_CODE in link:
            fnh = True

        web = get_response(link, ip_addresses)
        while not web:
            web = get_response(link, ip_addresses)

        if index == 0:
            file_mode = 'w'
        else:
            file_mode = 'a'

        skaters_table = scrape_from_page(web, 'div', 'id', 'statTable0-wrap')[0]
        # goalies_table = scrape_from_page(web, 'div', 'id', 'statTable1-wrap')

        players_df = get_dataframe_from_list(web, skaters_table)

        if SEASON_IN_PROGRESS:
            players_df.rename(columns={'Pos': 'Spot'}, inplace=True)

        delete_columns(players_df)
        add_total_row(players_df, fnh)
        players_df = players_df.fillna('')

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

    print(proxies)

    filename = get_filename()
    writer = pd.ExcelWriter(filename, engine='xlsxwriter')
    process_links(links, proxies)

    writer.save()

    open_file(filename)
    # open_file("reports/clean_rosters.txt")
