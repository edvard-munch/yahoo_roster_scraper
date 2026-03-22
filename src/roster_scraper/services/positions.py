import re

import bs4

from . import proxies


PLAYER_URL = "https://leftwinglock.com/players/index.php?p1={}&flag=y"

PARSER = "lxml"
POSITIONS_HEADER_STRING = "Positional Data"


def get_soup(proxies_list, name):
    params = {}

    if proxies_list:
        proxy = proxies.get_proxy(proxies_list)
        web = proxies.get_response(
            PLAYER_URL.format(name), params, proxies=proxies_list, proxy=proxy
        )

        while not web:
            proxy = proxies.get_proxy(proxies_list)
            web = proxies.get_response(
                PLAYER_URL.format(name), params, proxies=proxies_list, proxy=proxy
            )
    else:
        web = proxies.get_response(PLAYER_URL.format(name), params)

    return bs4.BeautifulSoup(web.content, PARSER)


def get_positional_data(proxies_list, name):
    soup = get_soup(proxies_list, name)
    html_header = soup.find("h4", string=re.compile(POSITIONS_HEADER_STRING))

    if html_header:
        table = html_header.find_next("table")

        table_headers = table.find("thead").find_all("th")
        rows = table.find("tbody").find_all("tr")
        headers_map = []
        output = {"name": name, "seasons": []}

        for header in table_headers:
            headers_map.append(header.string)

        for row in rows:
            season = {}
            for column_index, cell in enumerate(row):
                season[headers_map[column_index]] = cell.string

            output["seasons"].append(season)

        return output
