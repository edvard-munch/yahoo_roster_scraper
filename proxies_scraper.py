import random
import requests
import bs4


URL = 'https://free-proxy-list.net/'
PARSER = 'html.parser'
PROXIES_TABLE_CLASS = 'table table-striped table-bordered'
HTTPS_SUPPORT = 'yes'
PROTOCOLS = ['http', 'https']
TAGS = ['tr', 'td']


def scrape_proxies():

    response = requests.get(URL)
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
