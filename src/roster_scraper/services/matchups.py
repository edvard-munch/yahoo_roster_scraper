from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

import bs4


@dataclass
class MatchupsContext:
    columns: dict[str, tuple[int, int]]
    wide_column_width: int
    number_of_matchups_processed_message: str
    matchup_totals_parameter: str
    matchup_result_classes: str
    team_name_matchup_result_classes: str
    proxies_scraper: Any
    parse_full_page: Callable[..., tuple[bs4.BeautifulSoup, Any]]
    scrape_from_page: Callable[..., list[Any]]


def process_matchups(
    context: MatchupsContext,
    matchup_links,
    team_totals_dict,
    proxies,
    proxy=None,
) -> Any:
    number_of_matchups_processed_message = context.number_of_matchups_processed_message
    matchup_totals_parameter = context.matchup_totals_parameter
    matchup_result_classes = context.matchup_result_classes
    team_name_matchup_result_classes = context.team_name_matchup_result_classes
    proxies_scraper = context.proxies_scraper
    parse_full_page = context.parse_full_page
    scrape_from_page = context.scrape_from_page
    headers = []
    row_number = 0
    matchup_rows = [[]]

    if proxies and not proxy:
        proxy = proxies_scraper.get_proxy(proxies)
    elif not proxies:
        proxy = None

    for link_index, link in enumerate(matchup_links):
        soup, proxy = parse_full_page(link + matchup_totals_parameter, proxies, proxy)
        tables = scrape_from_page(soup, "table", "class", matchup_result_classes)

        if not tables:
            print(f"Skipping matchup: result table not found ({link})")
            continue

        table = tables[0]
        thead = table.find("thead")
        tbody = table.find("tbody")

        if not thead or not tbody:
            print(f"Skipping matchup: malformed table structure ({link})")
            continue

        if not headers:
            headers = thead.find_all("th")

            for header in headers:
                matchup_rows[row_number].append(header.string)

            row_number += 1
            matchup_rows.append([])

        rows = tbody.find_all("tr")
        number_of_cells = 0

        for row in rows:
            cells = row.find_all("td")

            if not number_of_cells:
                number_of_cells = len(cells)

            prognosis = {}

            for cell in cells:
                try:
                    name = cell.find("span", class_=team_name_matchup_result_classes).string
                    prognosis = team_totals_dict.get(name, {})

                except AttributeError:
                    name = cell.string

                matchup_rows[row_number].append(name)

            row_values = matchup_rows[row_number][1 : len(prognosis) + 1]
            prognosis_values = list(prognosis.values())

            for value_num, _ in enumerate(row_values):
                try:
                    value = float(row_values[value_num])
                except (ValueError, TypeError):
                    value = 0.0

                row_values[value_num] = value + prognosis_values[value_num]

            matchup_rows[row_number][1 : len(prognosis) + 1] = row_values

            row_number += 1
            matchup_rows.append([])

        print(number_of_matchups_processed_message.format(link_index + 1, len(matchup_links)))
        for _ in range(0, number_of_cells):
            matchup_rows[row_number].append(None)

        row_number += 1
        matchup_rows.append([])

    return matchup_rows, proxy
