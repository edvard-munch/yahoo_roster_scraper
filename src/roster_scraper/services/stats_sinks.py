from typing import Protocol

from . import google_sheet_tabs
from . import league_sheet_config
from . import league_spreadsheets


class StatsSink(Protocol):
    def write_team(self, team_name, table): ...

    def write_matchups(self, rows): ...

    def close(self): ...


class XlsxStatsSink:
    def __init__(self, workbook, core_output, matchups_context, matchups_sheet_name):
        self.workbook = workbook
        self.core_output = core_output
        self.matchups_context = matchups_context
        self.matchups_worksheet = workbook.add_worksheet(name=matchups_sheet_name)

    def write_team(self, team_name, table):
        sheet_name = self.core_output.verify_sheet_name(team_name)
        worksheet = self.workbook.add_worksheet(name=sheet_name)
        self.core_output.write_to_xlsx(table, worksheet)

    def write_matchups(self, rows):
        columns = self.matchups_context.columns
        width = self.matchups_context.wide_column_width
        self.matchups_worksheet.set_column(*columns["second"], width)
        self.matchups_worksheet.set_column(*columns["first"], width)

        for index, row in enumerate(rows):
            self.matchups_worksheet.write_row(index, 0, row)

    def close(self):
        self.workbook.close()


GOOGLE_SHEETS_VALUE_INPUT_OPTION = "RAW"
WIDE_COLUMN_PIXEL_SIZE = 150
FROZEN_HEADER_ROW_COUNT = 1


class GoogleSheetsStatsSink:
    def __init__(self, service, spreadsheet_id, config):
        league_sheet_config.validate_timezone(config.timezone)
        self.service = service
        self.spreadsheet_id = spreadsheet_id
        self.config = config
        self.team_tables = []
        self.matchup_rows = []
        self.closed = False

    def write_team(self, team_name, table):
        self._ensure_open()
        self.team_tables.append((team_name, table))

    def write_matchups(self, rows):
        self._ensure_open()
        self.matchup_rows = rows

    def close(self):
        if self.closed:
            return

        team_names = [team_name for team_name, _ in self.team_tables]
        team_tabs = google_sheet_tabs.sync_stats_tabs(
            self.service,
            self.spreadsheet_id,
            team_names,
        )
        value_ranges = []

        for team_tab, (_, table) in zip(team_tabs, self.team_tables, strict=True):
            value_ranges.append(
                {
                    "range": google_sheet_tabs.quote_tab_range(team_tab.title),
                    "values": table_to_rows(table),
                }
            )

        if self.matchup_rows:
            value_ranges.append(
                {
                    "range": google_sheet_tabs.quote_tab_range(
                        league_spreadsheets.MATCHUPS_SHEET_TITLE
                    ),
                    "values": normalize_rows(self.matchup_rows),
                }
            )

        if value_ranges:
            self.service.values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={
                    "valueInputOption": GOOGLE_SHEETS_VALUE_INPUT_OPTION,
                    "data": value_ranges,
                },
            ).execute()

        self._apply_formatting(team_tabs)
        previous_last_run = self.config.last_run
        self.config.last_run = league_sheet_config.build_last_run_timestamp(
            timezone=self.config.timezone
        )
        try:
            league_sheet_config.write_league_config(
                self.service,
                self.spreadsheet_id,
                self.config,
            )
        except Exception:
            self.config.last_run = previous_last_run
            raise
        self.closed = True

    def _apply_formatting(self, team_tabs):
        properties = google_sheet_tabs.get_sheet_properties(
            self.service,
            self.spreadsheet_id,
        )
        properties_by_title = {item["title"].casefold(): item for item in properties}
        requests = []

        matchups_title = league_spreadsheets.MATCHUPS_SHEET_TITLE
        matchups_properties = properties_by_title.get(matchups_title.casefold())
        if not matchups_properties:
            raise ValueError("MATCHUPS tab is missing after synchronization")
        requests.extend(
            build_format_requests(
                matchups_properties["sheetId"],
                start_column_index=0,
                end_column_index=2,
            )
        )

        for team_tab in team_tabs:
            team_properties = properties_by_title.get(team_tab.title.casefold())
            if not team_properties:
                raise ValueError(f"Team tab is missing after synchronization: {team_tab.title}")
            requests.extend(
                build_format_requests(
                    team_properties["sheetId"],
                    start_column_index=1,
                    end_column_index=2,
                )
            )

        self.service.batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"requests": requests},
        ).execute()

    def _ensure_open(self):
        if self.closed:
            raise RuntimeError("Cannot write to a closed Google Sheets stats sink")


def normalize_rows(rows):
    return [["" if value is None else value for value in row] for row in rows]


def table_to_rows(table):
    headers = list(table.keys())
    columns = [list(values) for values in table.values()]
    row_count = max((len(column) for column in columns), default=0)
    rows = [headers]

    for row_index in range(row_count):
        rows.append(
            [
                column[row_index]
                if row_index < len(column) and column[row_index] is not None
                else ""
                for column in columns
            ]
        )

    return rows


def build_format_requests(sheet_id, start_column_index, end_column_index):
    return [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": FROZEN_HEADER_ROW_COUNT},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": start_column_index,
                    "endIndex": end_column_index,
                },
                "properties": {"pixelSize": WIDE_COLUMN_PIXEL_SIZE},
                "fields": "pixelSize",
            }
        },
    ]
