import random
import requests
import sys
import bs4


PROXIES_URL = 'https://free-proxy-list.net/'
PARSER = 'html.parser'
PROXIES_TABLE_CLASS = 'table table-striped table-bordered'
HTTPS_SUPPORT = 'yes'
PROTOCOLS = ['http', 'https']
TAGS = ['tr', 'td']

CONNECTION_ERROR_MESSAGE = 'Connnection Error. Retry'
PROXIE_CONNECTION_ATTEMPT_MESSAGE = 'Trying with IP: {}'
PROXIES_LEFT_MESSAGE = 'Proxies left: {}'
REQUEST_TIMEOUT = 2

def scrape_proxies():
    response = requests.get(PROXIES_URL)
    soup = bs4.BeautifulSoup(response.content, PARSER)
    proxies = []
    rows = soup.find(class_=PROXIES_TABLE_CLASS).find_all(TAGS[0])

    for tr in rows:
        if (tr.contents[6].string == HTTPS_SUPPORT) and (tr.contents[0].name == TAGS[1]):
            proxy = f'{tr.contents[0].string}:{tr.contents[1].string}'
            proxies.append({PROTOCOLS[0]: proxy, PROTOCOLS[1]: proxy})

    return proxies


def get_proxy(proxies):
    if proxies:
        proxy_index = random.randint(0, len(proxies) - 1)
        return proxies[proxy_index]

    else:
        print('No free proxies available. Refresh proxies list and try again!')
        sys.exit(1)


def get_response(link, params, **proxie_data):
    if proxie_data:
        print(PROXIE_CONNECTION_ATTEMPT_MESSAGE.format(proxie_data['proxy']['http']))

        try:
            web = requests.get(link, params=params,
                               proxies=proxie_data['proxy'], timeout=REQUEST_TIMEOUT)

        except (requests.ConnectTimeout, OSError) as e:
            print(CONNECTION_ERROR_MESSAGE)
            proxie_data['proxies'].remove(proxie_data['proxy'])
            print(PROXIES_LEFT_MESSAGE.format(len(proxie_data["proxies"])))
            return None
    else:
        web = requests.get(link, params=params)

    return web
