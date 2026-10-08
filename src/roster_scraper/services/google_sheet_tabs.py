import re
from dataclasses import dataclass

from . import league_sheet_config
from . import league_spreadsheets


INVALID_TITLE_PATTERN = re.compile(r"[:\\/?*\[\]]")
MAX_TITLE_LENGTH = 100
DEFAULT_TEAM_TITLE = "Team"
DUPLICATE_TITLE_TEMPLATE = "{} ({})"
A1_SHEET_RANGE_TEMPLATE = "'{}'"
SHEET_METADATA_FIELDS = "sheets(properties(sheetId,title,hidden))"
RESERVED_TITLES = (
    league_spreadsheets.MATCHUPS_SHEET_TITLE,
    league_sheet_config.CONFIG_SHEET_TITLE,
)


@dataclass(frozen=True)
class TeamTab:
    team_name: str
    title: str


def sanitize_tab_title(team_name):
    title = INVALID_TITLE_PATTERN.sub("", str(team_name)).strip()
    return (title or DEFAULT_TEAM_TITLE)[:MAX_TITLE_LENGTH]


def build_team_tabs(team_names):
    used_titles = {title.casefold() for title in RESERVED_TITLES}
    team_tabs = []

    for team_name in team_names:
        base_title = sanitize_tab_title(team_name)
        title = base_title
        suffix_number = 2

        while title.casefold() in used_titles:
            suffix = f" ({suffix_number})"
            title = DUPLICATE_TITLE_TEMPLATE.format(
                base_title[: MAX_TITLE_LENGTH - len(suffix)],
                suffix_number,
            )
            suffix_number += 1

        used_titles.add(title.casefold())
        team_tabs.append(TeamTab(team_name=str(team_name), title=title))

    return team_tabs


def quote_tab_range(title):
    return A1_SHEET_RANGE_TEMPLATE.format(title.replace("'", "''"))


def get_sheet_properties(service, spreadsheet_id):
    response = service.get(
        spreadsheetId=spreadsheet_id,
        fields=SHEET_METADATA_FIELDS,
    ).execute()
    return [sheet["properties"] for sheet in response.get("sheets", [])]


def sync_stats_tabs(service, spreadsheet_id, team_names):
    planned_tabs = build_team_tabs(team_names)
    existing_properties = get_sheet_properties(service, spreadsheet_id)
    existing_by_title = {
        properties["title"].casefold(): properties for properties in existing_properties
    }
    desired_keys = {tab.title.casefold() for tab in planned_tabs}
    reserved_keys = {title.casefold() for title in RESERVED_TITLES}
    requests = []

    for title in RESERVED_TITLES:
        if title.casefold() not in existing_by_title:
            properties = {"title": title}
            if title == league_sheet_config.CONFIG_SHEET_TITLE:
                properties["hidden"] = True
            requests.append({"addSheet": {"properties": properties}})

    resolved_tabs = []
    for tab in planned_tabs:
        existing = existing_by_title.get(tab.title.casefold())
        if existing:
            resolved_tabs.append(TeamTab(tab.team_name, existing["title"]))
        else:
            requests.append({"addSheet": {"properties": {"title": tab.title}}})
            resolved_tabs.append(tab)

    for properties in existing_properties:
        title_key = properties["title"].casefold()
        if title_key not in reserved_keys and title_key not in desired_keys:
            requests.append({"deleteSheet": {"sheetId": properties["sheetId"]}})

    config_properties = existing_by_title.get(league_sheet_config.CONFIG_SHEET_TITLE.casefold())
    if config_properties and not config_properties.get("hidden", False):
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": config_properties["sheetId"],
                        "hidden": True,
                    },
                    "fields": "hidden",
                }
            }
        )

    if requests:
        service.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

    clear_ranges = [quote_tab_range(league_spreadsheets.MATCHUPS_SHEET_TITLE)]
    clear_ranges.extend(quote_tab_range(tab.title) for tab in resolved_tabs)
    service.values().batchClear(
        spreadsheetId=spreadsheet_id,
        body={"ranges": clear_ranges},
    ).execute()

    return resolved_tabs
