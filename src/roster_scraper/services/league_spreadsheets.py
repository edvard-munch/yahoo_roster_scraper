from . import league_sheet_config


SPREADSHEET_TITLE_TEMPLATE = "{} Stats"
FALLBACK_LEAGUE_NAME_TEMPLATE = "Yahoo Hockey League {}"
SPREADSHEET_MIME_TYPE = "application/vnd.google-apps.spreadsheet"
APPLICATION_PROPERTY = "roster_scraper"
APPLICATION_VALUE = "league_stats"
LEAGUE_PROPERTY = "league_id"
MATCHUPS_SHEET_TITLE = "MATCHUPS"
DISCOVERY_PAGE_SIZE = 2


def validate_league_id(league_id):
    if not isinstance(league_id, str) or not league_id.isascii() or not league_id.isdigit():
        raise ValueError("League ID must be a non-empty string of ASCII digits")


def get_spreadsheet_title(config):
    league_name = config.league_name.strip() or FALLBACK_LEAGUE_NAME_TEMPLATE.format(
        config.league_id
    )
    return SPREADSHEET_TITLE_TEMPLATE.format(league_name)


def get_spreadsheet(sheets_service, spreadsheet_id):
    return sheets_service.get(
        spreadsheetId=spreadsheet_id,
        fields="spreadsheetId,spreadsheetUrl,properties.title,sheets.properties",
    ).execute()


def find_league_spreadsheet(drive_service, league_id):
    validate_league_id(league_id)
    query = (
        f"trashed = false and mimeType = '{SPREADSHEET_MIME_TYPE}' "
        f"and appProperties has {{ key='{APPLICATION_PROPERTY}' and value='{APPLICATION_VALUE}' }} "
        f"and appProperties has {{ key='{LEAGUE_PROPERTY}' and value='{league_id}' }}"
    )
    spreadsheet_ids = []
    page_token = None

    while True:
        response = drive_service.list(
            q=query,
            spaces="drive",
            pageSize=DISCOVERY_PAGE_SIZE,
            pageToken=page_token,
            fields="nextPageToken,files(id)",
        ).execute()
        spreadsheet_ids.extend(file["id"] for file in response.get("files", []))
        if len(spreadsheet_ids) > 1:
            raise ValueError(f"Multiple stats spreadsheets found for league {league_id}")
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return spreadsheet_ids[0] if spreadsheet_ids else None


def create_spreadsheet(sheets_service, drive_service, config):
    validate_league_id(config.league_id)
    league_sheet_config.validate_timezone(config.timezone)
    response = sheets_service.create(
        body={
            "properties": {"title": get_spreadsheet_title(config)},
            "sheets": [
                {"properties": {"title": MATCHUPS_SHEET_TITLE}},
                {"properties": {"title": league_sheet_config.CONFIG_SHEET_TITLE, "hidden": True}},
            ],
        },
        fields="spreadsheetId",
    ).execute()
    spreadsheet_id = response["spreadsheetId"]
    # Tag before writing config: a failed config write must not cause another file to be created.
    drive_service.update(
        fileId=spreadsheet_id,
        body={
            "appProperties": {
                APPLICATION_PROPERTY: APPLICATION_VALUE,
                LEAGUE_PROPERTY: config.league_id,
            }
        },
        fields="id",
    ).execute()
    league_sheet_config.write_league_config(sheets_service, spreadsheet_id, config)
    return spreadsheet_id


def resolve_league_spreadsheet(sheets_service, drive_service, config):
    spreadsheet_id = find_league_spreadsheet(drive_service, config.league_id)
    if spreadsheet_id is None:
        return create_spreadsheet(sheets_service, drive_service, config)

    spreadsheet = get_spreadsheet(sheets_service, spreadsheet_id)
    stored_config = league_sheet_config.read_league_config(sheets_service, spreadsheet_id)
    if stored_config.league_id != config.league_id:
        raise ValueError(f"Spreadsheet {spreadsheet_id} has missing or mismatched league config")

    # Keep the spreadsheet's timestamp preference when refreshed through the CLI.
    league_sheet_config.validate_timezone(stored_config.timezone)
    config.timezone = stored_config.timezone

    expected_title = get_spreadsheet_title(config)
    current_title = spreadsheet.get("properties", {}).get("title")
    if current_title != expected_title:
        drive_service.update(
            fileId=spreadsheet_id,
            body={"name": expected_title},
            fields="id",
        ).execute()

    return spreadsheet_id
