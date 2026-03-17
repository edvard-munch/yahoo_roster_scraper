import bs4
import json
from dataclasses import dataclass


@dataclass
class RosterWorkflowContext:
    format_choices: dict
    parser: str
    proxies_scraper: object
    schedule_scraper: object
    core_parsing: object
    core_output: object
    write_to_google_sheet: object
    workbook: object
    scoring_columns: list
    empty_spot_string: str
    number_of_teams_processed_message: str
    positions_filename: str
    get_team_name: object
    get_headers: object
    get_body: object
    process_matchups: object


def process_links(context,
                  links,
                  proxies,
                  choice,
                  stats_page,
                  matchup_links=None,
                  schedule=None,
                  matchups_worksheet=None):
    format_choices = context.format_choices
    parser = context.parser
    proxies_scraper = context.proxies_scraper
    schedule_scraper = context.schedule_scraper
    core_parsing = context.core_parsing
    core_output = context.core_output
    write_to_google_sheet = context.write_to_google_sheet
    workbook = context.workbook
    scoring_columns = context.scoring_columns
    empty_spot_string = context.empty_spot_string
    number_of_teams_processed_message = context.number_of_teams_processed_message
    positions_filename = context.positions_filename
    get_team_name = context.get_team_name
    get_headers = context.get_headers
    get_body = context.get_body
    process_matchups = context.process_matchups
    team_totals_dict = {}
    missing_schedule_teams = set()

    if choice == format_choices['xlsx']:
        schedule = schedule_scraper.apply_team_aliases(schedule or {})

    if proxies:
        proxy = proxies_scraper.get_proxy(proxies)

    json_dump_data = {}
    for index, link in enumerate(links):
        if proxies:
            web = proxies_scraper.get_response(link,
                                               stats_page,
                                               proxies=proxies,
                                               proxy=proxy)

            while not web:
                proxy = proxies_scraper.get_proxy(proxies)
                web = proxies_scraper.get_response(link,
                                                   stats_page,
                                                   proxies=proxies,
                                                   proxy=proxy)

        else:
            web = proxies_scraper.get_response(link, stats_page)

        soup = bs4.BeautifulSoup(web.text, parser)

        team_name = get_team_name(soup, fallback_name=f'Team {index + 1}')

        if choice == format_choices['xlsx']:
            headers = get_headers(soup)
            body = get_body(soup, schedule, missing_schedule_teams)
            table = core_parsing.map_headers_to_body(headers, body, True)

            sheet_name = core_output.verify_sheet_name(team_name)
            worksheet = workbook.add_worksheet(name=sheet_name)
            core_output.write_to_xlsx(table, worksheet)

            team_totals = {}
            for col in scoring_columns:
                if col in headers.keys():
                    team_totals[col] = table[col][-1]
            team_totals_dict[team_name.strip()] = team_totals

        else:
            bodies = soup.find_all('tbody')
            file_mode = 'w' if index == 0 else 'a'

            if choice == format_choices['txt']:
                data = core_parsing.parse_clean_names(bodies[1:])
                core_output.write_roster_to_txt(
                    data,
                    file_mode,
                    team_name,
                    empty_spot_string,
                )

            elif choice == format_choices['json'] or choice == format_choices['google_sheets']:
                json_dump_data[team_name] = core_parsing.parse_for_json(bodies[1])

        print(number_of_teams_processed_message.format(index + 1, len(links)))

    if choice == format_choices['json'] or choice == format_choices['google_sheets']:
        with open(positions_filename, 'w') as text_file:
            json.dump(json_dump_data, text_file, indent=2)

    if choice == format_choices['google_sheets']:
        write_to_google_sheet.google(positions_filename)

    if choice == format_choices['xlsx']:
        if missing_schedule_teams:
            mapped_preview = {
                team: schedule_scraper.TEAM_CODE_ALIASES.get(team, team)
                for team in sorted(missing_schedule_teams)
            }
            print(f'Schedule teams not found: {mapped_preview}')

        process_matchups(matchup_links, team_totals_dict, proxies, matchups_worksheet)
