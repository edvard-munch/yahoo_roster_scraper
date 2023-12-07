import bs4
import re

import proxies_scraper


PLAYER_URL = 'https://leftwinglock.com/players/index.php?p1={}&flag=y'

PARSER = 'lxml'
POSITIONS_HEADER_STRING = 'Positional Data'


def get_soup(proxies, name):
    params = {}

    if proxies:
        proxy = proxies_scraper.get_proxy(proxies)
        web = proxies_scraper.get_response(PLAYER_URL.format(name), params,  proxies=proxies, proxy=proxy)

        while not web:
            proxy = proxies_scraper.get_proxy(proxies)
            web = proxies_scraper.get_response(PLAYER_URL.format(name), params, proxies=proxies, proxy=proxy)
    else:
        web = proxies_scraper.get_response(PLAYER_URL.format(name), params)

    return bs4.BeautifulSoup(web.content, PARSER)


def get_positional_data(proxies, name):
    soup = get_soup(proxies, name)
    html_header = soup.find('h4', string=re.compile(POSITIONS_HEADER_STRING))

    if html_header:
        table = html_header.find_next('table')

        table_headers = table.find('thead').find_all('th')
        rows = table.find('tbody').find_all('tr')
        headers_map = []
        output = {'name': name, 'seasons': []}

        for header in table_headers:
            headers_map.append(header.string)

        for row_index, row in enumerate(rows):
            season = {}
            for column_index, cell in enumerate(row):
                season[headers_map[column_index]] = cell.string

            output['seasons'].append(season)

        return output
