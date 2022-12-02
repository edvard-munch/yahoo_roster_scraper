import bs4
import proxies_scraper

SCHEDULE_URL = 'https://leftwinglock.com/schedules'
PARSER = 'lxml'
SCHEDULE_TABLE_CLASS = 'styled-table'


def get_schedule(proxies):
    params = {}
    if proxies:
        proxy = proxies_scraper.get_proxy(proxies)
        web = proxies_scraper.get_response(SCHEDULE_URL, params,  proxies=proxies, proxy=proxy)

        while not web:
            proxy = proxies_scraper.get_proxy(proxies)
            web = proxies_scraper.get_response(SCHEDULE_URL, params, proxies=proxies, proxy=proxy)
    else:
        web = proxies_scraper.get_response(SCHEDULE_URL, params)

    soup = bs4.BeautifulSoup(web.content, PARSER)
    tables = soup.find_all(class_=SCHEDULE_TABLE_CLASS)
    headers_map = {}
    team_schedules = {}

    for table in tables:
            headers = table.find('thead').find_all('th')
            for header_index, header in enumerate(headers):
                headers_map[header_index] = header.string

            rows = table.find('tbody').find_all('tr')
            for row in rows:
                for row_index, cell in enumerate(row):
                    if row_index == 0:
                        team_name = cell.string
                        team_schedules[team_name] = {}
                    else:    
                        team_schedules[team_name][headers_map[row_index]] = cell.string

    return team_schedules                    
