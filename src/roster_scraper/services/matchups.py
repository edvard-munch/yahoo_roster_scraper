from dataclasses import dataclass


@dataclass
class MatchupsContext:
    columns: dict
    wide_column_width: int
    number_of_matchups_processed_message: str
    matchup_totals_parameter: str
    matchup_result_classes: str
    team_name_matchup_result_classes: str
    proxies_scraper: object
    parse_full_page: object
    scrape_from_page: object


def process_matchups(context,
                     matchup_links,
                     team_totals_dict,
                     proxies,
                     worksheet):
    columns = context.columns
    wide_column_width = context.wide_column_width
    number_of_matchups_processed_message = context.number_of_matchups_processed_message
    matchup_totals_parameter = context.matchup_totals_parameter
    matchup_result_classes = context.matchup_result_classes
    team_name_matchup_result_classes = context.team_name_matchup_result_classes
    proxies_scraper = context.proxies_scraper
    parse_full_page = context.parse_full_page
    scrape_from_page = context.scrape_from_page
    worksheet.set_column(*columns['second'], wide_column_width)
    worksheet.set_column(*columns['first'], wide_column_width)
    headers = []
    worksheet_row_number = 0
    worksheet_rows = [[]]

    if proxies:
        proxy = proxies_scraper.get_proxy(proxies)
    else:
        proxy = None

    for link_index, link in enumerate(matchup_links):
        soup, proxy = parse_full_page(link + matchup_totals_parameter, proxies, proxy)
        table = scrape_from_page(soup, 'table', 'class', matchup_result_classes)[0]

        if not headers:
            headers = table.find('thead').find_all('th')

            for header in headers:
                worksheet_rows[worksheet_row_number].append(header.string)

            worksheet_row_number += 1
            worksheet_rows.append([])

        rows = table.find('tbody').find_all('tr')
        number_of_cells = 0

        for row in rows:
            cells = row.find_all('td')

            if not number_of_cells:
                number_of_cells = len(cells)

            prognosis = {}

            for cell in cells:
                try:
                    name = cell.find('span', class_=team_name_matchup_result_classes).string
                    prognosis = team_totals_dict.get(name, {})

                except AttributeError:
                    name = cell.string

                worksheet_rows[worksheet_row_number].append(name)

            row_values = worksheet_rows[worksheet_row_number][1:len(prognosis) + 1]
            prognosis_values = list(prognosis.values())

            for value_num, _ in enumerate(row_values):
                try:
                    value = float(row_values[value_num])
                except (ValueError, TypeError):
                    value = 0.0

                row_values[value_num] = value + prognosis_values[value_num]

            worksheet_rows[worksheet_row_number][1:len(prognosis) + 1] = row_values

            worksheet_row_number += 1
            worksheet_rows.append([])

        print(number_of_matchups_processed_message.format(link_index + 1, len(matchup_links)))
        for _ in range(0, number_of_cells):
            worksheet_rows[worksheet_row_number].append(None)

        worksheet_row_number += 1
        worksheet_rows.append([])

    for index, row in enumerate(worksheet_rows):
        worksheet.write_row(index, 0, row)
