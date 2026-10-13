import datetime
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


CONFIG_SHEET_TITLE = "_config"
DEFAULT_TIMEZONE = "UTC"
TIMESTAMP_PRECISION = "seconds"

LEAGUE_ID_KEY = "league_id"
LEAGUE_NAME_KEY = "league_name"
SEASON_KEY = "season"
START_DATE_OVERRIDE_KEY = "start_date_override"
LAST_RUN_KEY = "last_run"
TIMEZONE_KEY = "timezone"
RUN_STATUS_KEY = "run_status"
RUN_STARTED_AT_KEY = "run_started_at"
LAST_ERROR_KEY = "last_error"

RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETE = "complete"
RUN_STATUS_FAILED = "failed"


@dataclass
class LeagueConfig:
    league_id: str = ""
    league_name: str = ""
    season: str = ""
    start_date_override: str | None = None
    last_run: str | None = None
    timezone: str = DEFAULT_TIMEZONE
    run_status: str | None = None
    run_started_at: str | None = None
    last_error: str | None = None
    extras: dict[str, str] = field(default_factory=dict)


def config_to_rows(config):
    return [
        [LEAGUE_ID_KEY, config.league_id],
        [LEAGUE_NAME_KEY, config.league_name],
        [SEASON_KEY, config.season],
        [START_DATE_OVERRIDE_KEY, config.start_date_override or ""],
        [LAST_RUN_KEY, config.last_run or ""],
        [TIMEZONE_KEY, config.timezone],
        [RUN_STATUS_KEY, config.run_status or ""],
        [RUN_STARTED_AT_KEY, config.run_started_at or ""],
        [LAST_ERROR_KEY, config.last_error or ""],
        *[[key, value] for key, value in config.extras.items()],
    ]


def config_from_rows(rows):
    config = LeagueConfig()

    for row in rows:
        if not row:
            continue

        key = row[0].strip() if row[0] else ""
        value = row[1].strip() if len(row) > 1 and row[1] else ""

        if not key:
            continue

        if key == LEAGUE_ID_KEY:
            config.league_id = value
        elif key == LEAGUE_NAME_KEY:
            config.league_name = value
        elif key == SEASON_KEY:
            config.season = value
        elif key == START_DATE_OVERRIDE_KEY:
            config.start_date_override = value or None
        elif key == LAST_RUN_KEY:
            config.last_run = value or None
        elif key == TIMEZONE_KEY:
            config.timezone = value or DEFAULT_TIMEZONE
        elif key == RUN_STATUS_KEY:
            config.run_status = value or None
        elif key == RUN_STARTED_AT_KEY:
            config.run_started_at = value or None
        elif key == LAST_ERROR_KEY:
            config.last_error = value or None
        else:
            config.extras[key] = value

    return config


def validate_timezone(timezone):
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as error:
        raise ValueError(
            "_config timezone must be a valid IANA name, e.g. Europe/Moscow"
        ) from error


def build_last_run_timestamp(now=None, timezone=DEFAULT_TIMEZONE):
    zone = validate_timezone(timezone)
    now = now if now is not None else datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timestamp source must include timezone information")
    return now.astimezone(zone).isoformat(timespec=TIMESTAMP_PRECISION)


def read_league_config(service, spreadsheet_id):
    response = (
        service.values().get(spreadsheetId=spreadsheet_id, range=CONFIG_SHEET_TITLE).execute()
    )

    return config_from_rows(response.get("values", []))


def write_league_config(service, spreadsheet_id, config):
    service.values().update(
        spreadsheetId=spreadsheet_id,
        range=CONFIG_SHEET_TITLE,
        valueInputOption="RAW",
        body={"values": config_to_rows(config)},
    ).execute()
