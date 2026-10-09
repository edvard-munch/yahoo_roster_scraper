import datetime
import xlsxwriter

from roster_scraper import application
from roster_scraper import runtime as scraper_runtime
from roster_scraper.services.yahoo_scraper import FORMAT_CHOICES, POSITIONS_FILENAME
from roster_scraper.services import google_api_auth
from roster_scraper.services import proxies as proxies_scraper
from roster_scraper.services import league_sheet_config
from roster_scraper.services import league_spreadsheets
from roster_scraper.services import stats_sinks
from roster_scraper.core import output as core_output


PROXY_CHOICES = {"Y": True, "n": False}
FULL_STATS_OUTPUT_CHOICES = {"xlsx": "1", "google_sheets": "2"}


SEASON_CHOICES = {"preseason": "1", "just_started": "2", "in_season": "3"}
SEASON_MODES = {
    choice: application.SEASON_MODES_BY_NAME[name] for name, choice in SEASON_CHOICES.items()
}
SEASON_MODE_NAMES = {SEASON_MODES[choice]: name for name, choice in SEASON_CHOICES.items()}


FORMAT_CHOICE_MESSAGE = (
    "Input 1 for full stats tables\n"
    "Input 2 for simple txt rosters\n"
    "Input 3 for positions in JSON file\n"
    "Input 4 for writing positions to Google Sheets:\n"
)

FULL_STATS_OUTPUT_MESSAGE = (
    "Select full stats output:\nInput 1 for a local xlsx file\nInput 2 for Google Sheets:\n"
)
PROXIES_CHOICE_MESSAGE = "Use proxies? Y/n:\n"
SEASON_MODE_MESSAGE = (
    "Select season mode:\n"
    "Input 1 for preseason/offseason\n"
    "Input 2 for season just started\n"
    "Input 3 for in-season:\n"
)
INPUT_LEAGUE_ID_MESSAGE = "Input league's ID:\n"
INPUT_SCHEDULE_START_DATE_MESSAGE = (
    "Input schedule start date override YYYY-MM-DD (Enter for today; use tomorrow to skip today):\n"
)
SCHEDULE_START_DATE_FORMAT = "%Y-%m-%d"
SCHEDULE_START_DATE_INVALID_MESSAGE = "Invalid date; expected YYYY-MM-DD. Please try again:\n"
INCORRECT_CHOICE_MESSAGE = "Please select a correct option"
GOOGLE_STATS_SPREADSHEET_URL_TEMPLATE = "https://docs.google.com/spreadsheets/d/{}"
GOOGLE_STATS_SPREADSHEET_MESSAGE = "Google stats spreadsheet: {}"

TXT_FILENAME = "reports/clean_rosters.txt"


SCHEDULE_START_DATE_OVERRIDE_MESSAGE = "Using schedule start date override: {}"


def validate_input(message, choices):
    choice = input(message)

    if choice in choices:
        return choice
    else:
        print(INCORRECT_CHOICE_MESSAGE)
        return None


def prompt_season_mode():
    season_choice = validate_input(SEASON_MODE_MESSAGE, SEASON_CHOICES.values())

    while not season_choice:
        season_choice = validate_input(SEASON_MODE_MESSAGE, SEASON_CHOICES.values())

    return SEASON_MODES[season_choice]


def prompt_full_stats_output():
    output_choice = validate_input(FULL_STATS_OUTPUT_MESSAGE, FULL_STATS_OUTPUT_CHOICES.values())

    while not output_choice:
        output_choice = validate_input(
            FULL_STATS_OUTPUT_MESSAGE, FULL_STATS_OUTPUT_CHOICES.values()
        )

    return output_choice


def get_league_name(soup):
    if not soup or not soup.title:
        return ""
    return soup.title.get_text(strip=True).split("|", 1)[0].strip()


def build_google_league_config(league_id, league_soup, season_mode, start_date_override):
    return league_sheet_config.LeagueConfig(
        league_id=league_id,
        league_name=get_league_name(league_soup),
        season=SEASON_MODE_NAMES[season_mode],
        start_date_override=start_date_override.isoformat() if start_date_override else None,
    )


def prompt_schedule_start_date_override():
    while True:
        raw_value = input(INPUT_SCHEDULE_START_DATE_MESSAGE).strip()

        if not raw_value:
            return None

        try:
            parsed_date = datetime.datetime.strptime(raw_value, SCHEDULE_START_DATE_FORMAT).date()
        except ValueError:
            print(SCHEDULE_START_DATE_INVALID_MESSAGE)
            continue

        print(SCHEDULE_START_DATE_OVERRIDE_MESSAGE.format(parsed_date))
        return parsed_date


def main():
    season_mode = prompt_season_mode()

    use_proxies_choice = validate_input(PROXIES_CHOICE_MESSAGE, PROXY_CHOICES)

    while not use_proxies_choice:
        use_proxies_choice = validate_input(PROXIES_CHOICE_MESSAGE, PROXY_CHOICES)

    use_proxies = PROXY_CHOICES[use_proxies_choice]

    if use_proxies:
        proxies = proxies_scraper.scrape_proxies()
    else:
        proxies = []

    league_id = input(INPUT_LEAGUE_ID_MESSAGE)
    scrape_dependencies = scraper_runtime.build_default_scrape_dependencies()
    prepared_league = application.prepare_league(
        league_id, season_mode, proxies, scrape_dependencies
    )

    while not prepared_league:
        league_id = input(INPUT_LEAGUE_ID_MESSAGE)
        prepared_league = application.prepare_league(
            league_id, season_mode, proxies, scrape_dependencies
        )

    choice = validate_input(FORMAT_CHOICE_MESSAGE, FORMAT_CHOICES.values())
    while not choice:
        choice = validate_input(FORMAT_CHOICE_MESSAGE, FORMAT_CHOICES.values())

    full_stats_output = None
    start_date_override = None
    if choice == FORMAT_CHOICES["xlsx"]:
        full_stats_output = prompt_full_stats_output()
        start_date_override = prompt_schedule_start_date_override()

    matchups_context = scraper_runtime.build_default_matchups_context()
    stats_sink = None
    filename = None

    if full_stats_output == FULL_STATS_OUTPUT_CHOICES["xlsx"]:
        filename = core_output.get_filename()
        workbook = xlsxwriter.Workbook(filename)
        stats_sink = stats_sinks.XlsxStatsSink(
            workbook,
            core_output,
            matchups_context,
            league_spreadsheets.MATCHUPS_SHEET_TITLE,
        )
    elif full_stats_output == FULL_STATS_OUTPUT_CHOICES["google_sheets"]:
        sheets_service = google_api_auth.sheet_service()
        drive_service = google_api_auth.drive_service()
        google_config = build_google_league_config(
            league_id,
            prepared_league.soup,
            season_mode,
            start_date_override,
        )
        spreadsheet_id = league_spreadsheets.resolve_league_spreadsheet(
            sheets_service,
            drive_service,
            google_config,
        )
        stats_sink = stats_sinks.GoogleSheetsStatsSink(
            sheets_service,
            spreadsheet_id,
            google_config,
        )
        print(
            GOOGLE_STATS_SPREADSHEET_MESSAGE.format(
                GOOGLE_STATS_SPREADSHEET_URL_TEMPLATE.format(spreadsheet_id)
            )
        )

    config = application.ScrapeConfig(
        league_id=league_id,
        season_mode=season_mode,
        output_format=choice,
        start_date_override=start_date_override,
    )
    application.run_scrape(
        config, prepared_league, matchups_context, scrape_dependencies, stats_sink
    )

    if filename:
        core_output.open_file(filename)
    elif choice == FORMAT_CHOICES["txt"]:
        core_output.open_file(TXT_FILENAME)
    elif choice == FORMAT_CHOICES["json"]:
        core_output.open_file(POSITIONS_FILENAME)


if __name__ == "__main__":
    main()
