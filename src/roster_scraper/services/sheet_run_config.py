import datetime
from dataclasses import dataclass

from roster_scraper import application

from . import league_sheet_config


START_DATE_FORMAT = "%Y-%m-%d"


class SheetConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SheetRunConfig:
    scrape_config: application.ScrapeConfig
    league_config: league_sheet_config.LeagueConfig


def validate_league_id(league_id):
    if not isinstance(league_id, str) or not league_id.isascii() or not league_id.isdigit():
        raise SheetConfigError("_config league_id must contain ASCII digits")


def parse_start_date_override(value):
    if not value:
        return None

    try:
        parsed_date = datetime.datetime.strptime(value, START_DATE_FORMAT).date()
    except ValueError as err:
        raise SheetConfigError("_config start_date_override must use YYYY-MM-DD") from err

    if parsed_date.isoformat() != value:
        raise SheetConfigError("_config start_date_override must use YYYY-MM-DD")
    return parsed_date


def build_sheet_run_config(config, full_stats_format):
    validate_league_id(config.league_id)
    try:
        league_sheet_config.validate_timezone(config.timezone)
    except ValueError as error:
        raise SheetConfigError(str(error)) from error

    try:
        season_mode = application.SEASON_MODES_BY_NAME[config.season]
    except KeyError as err:
        allowed = ", ".join(application.SEASON_MODES_BY_NAME)
        raise SheetConfigError(f"_config season must be one of: {allowed}") from err

    if not full_stats_format:
        raise SheetConfigError("Full stats output format is required")

    scrape_config = application.ScrapeConfig(
        league_id=config.league_id,
        season_mode=season_mode,
        output_format=full_stats_format,
        start_date_override=parse_start_date_override(config.start_date_override),
    )
    return SheetRunConfig(scrape_config=scrape_config, league_config=config)


def load_sheet_run_config(service, spreadsheet_id, full_stats_format):
    config = league_sheet_config.read_league_config(service, spreadsheet_id)
    return build_sheet_run_config(config, full_stats_format)
