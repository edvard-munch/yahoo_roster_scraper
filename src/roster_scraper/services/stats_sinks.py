from typing import Protocol


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
