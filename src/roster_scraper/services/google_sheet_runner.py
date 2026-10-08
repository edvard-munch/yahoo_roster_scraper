from roster_scraper import application

from . import sheet_run_config
from . import stats_sinks


class LeaguePreparationError(RuntimeError):
    pass


def run_google_sheet_scrape(
    sheets_service,
    spreadsheet_id,
    scrape_dependencies,
    matchups_context,
    proxies=None,
    current_proxy=None,
):
    if not spreadsheet_id:
        raise ValueError("Spreadsheet ID is required")

    sheet_config = sheet_run_config.load_sheet_run_config(
        sheets_service,
        spreadsheet_id,
        scrape_dependencies.xlsx_format,
    )
    prepared_league = application.prepare_league(
        sheet_config.scrape_config.league_id,
        sheet_config.scrape_config.season_mode,
        proxies or [],
        scrape_dependencies,
        current_proxy=current_proxy,
    )

    if not prepared_league:
        raise LeaguePreparationError(
            f"League {sheet_config.scrape_config.league_id} could not be prepared"
        )

    stats_sink = stats_sinks.GoogleSheetsStatsSink(
        sheets_service,
        spreadsheet_id,
        sheet_config.league_config,
    )
    return application.run_scrape(
        sheet_config.scrape_config,
        prepared_league,
        matchups_context,
        scrape_dependencies,
        stats_sink,
    )
