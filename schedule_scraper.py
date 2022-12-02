import bs4
import requests

SCHEDULE_URL = 'https://leftwinglock.com/schedules'
PARSER = 'lxml'
SCHEDULE_TABLE_CLASS = 'styled-table'


def get_schedule():
    web = requests.get(SCHEDULE_URL)
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
