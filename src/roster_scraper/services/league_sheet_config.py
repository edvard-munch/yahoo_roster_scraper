import datetime
from dataclasses import dataclass, field


CONFIG_SHEET_TITLE = "_config"
LAST_RUN_FORMAT = "%Y-%m-%dT%H:%M:%S"

LEAGUE_ID_KEY = "league_id"
SEASON_KEY = "season"
START_DATE_OVERRIDE_KEY = "start_date_override"
LAST_RUN_KEY = "last_run"


@dataclass
class LeagueConfig:
    league_id: str = ""
    season: str = ""
    start_date_override: str | None = None
    last_run: str | None = None
    extras: dict[str, str] = field(default_factory=dict)


def config_to_rows(config):
    return [
        [LEAGUE_ID_KEY, config.league_id],
        [SEASON_KEY, config.season],
        [START_DATE_OVERRIDE_KEY, config.start_date_override or ""],
        [LAST_RUN_KEY, config.last_run or ""],
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
        elif key == SEASON_KEY:
            config.season = value
        elif key == START_DATE_OVERRIDE_KEY:
            config.start_date_override = value or None
        elif key == LAST_RUN_KEY:
            config.last_run = value or None
        else:
            config.extras[key] = value

    return config


def build_last_run_timestamp(now=None):
    now = now or datetime.datetime.now()
    return now.strftime(LAST_RUN_FORMAT)


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
