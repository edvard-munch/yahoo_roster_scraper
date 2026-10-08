from roster_scraper import application

from . import league_sheet_config
from . import sheet_run_config
from . import stats_sinks


class LeaguePreparationError(RuntimeError):
    pass


MAX_ERROR_MESSAGE_LENGTH = 5000


def format_run_error(error):
    return f"{type(error).__name__}: {error}"[:MAX_ERROR_MESSAGE_LENGTH]


def write_run_status(sheets_service, spreadsheet_id, config, status, error=None):
    config.run_status = status
    config.last_error = format_run_error(error) if error else None
    league_sheet_config.write_league_config(sheets_service, spreadsheet_id, config)


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
    config = sheet_config.league_config
    config.run_started_at = league_sheet_config.build_last_run_timestamp()
    write_run_status(
        sheets_service,
        spreadsheet_id,
        config,
        league_sheet_config.RUN_STATUS_RUNNING,
    )

    try:
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
            config,
        )
        result = application.run_scrape(
            sheet_config.scrape_config,
            prepared_league,
            matchups_context,
            scrape_dependencies,
            stats_sink,
        )
        write_run_status(
            sheets_service,
            spreadsheet_id,
            config,
            league_sheet_config.RUN_STATUS_COMPLETE,
        )
        return result
    except Exception as error:
        try:
            write_run_status(
                sheets_service,
                spreadsheet_id,
                config,
                league_sheet_config.RUN_STATUS_FAILED,
                error,
            )
        except Exception as status_error:
            error.add_note(f"Failed to write sheet run status: {status_error}")
        raise
