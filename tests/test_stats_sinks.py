from types import SimpleNamespace

from roster_scraper.services import stats_sinks


class WorksheetSpy:
    def __init__(self, name):
        self.name = name
        self.columns = []
        self.rows = []

    def set_column(self, *args):
        self.columns.append(args)

    def write_row(self, index, col, row):
        self.rows.append((index, col, list(row)))


class WorkbookSpy:
    def __init__(self):
        self.worksheets = []
        self.closed = False

    def add_worksheet(self, name):
        worksheet = WorksheetSpy(name)
        self.worksheets.append(worksheet)
        return worksheet

    def close(self):
        self.closed = True


class OutputSpy:
    def __init__(self):
        self.calls = []

    def verify_sheet_name(self, name):
        return name.replace("/", "")

    def write_to_xlsx(self, table, worksheet):
        self.calls.append((table, worksheet.name))


def build_sink():
    workbook = WorkbookSpy()
    output = OutputSpy()
    context = SimpleNamespace(
        columns={"first": (0, 0), "second": (1, 1)},
        wide_column_width=25,
    )
    sink = stats_sinks.XlsxStatsSink(workbook, output, context, "MATCHUPS")
    return sink, workbook, output


def test_xlsx_sink_creates_matchups_first_and_writes_team_table():
    sink, workbook, output = build_sink()
    table = {"Team": ["BOS"], "G": [1]}

    sink.write_team("BOS/Stats", table)

    assert [sheet.name for sheet in workbook.worksheets] == ["MATCHUPS", "BOSStats"]
    assert output.calls == [(table, "BOSStats")]


def test_xlsx_sink_writes_matchups_with_existing_layout():
    sink, workbook, _ = build_sink()
    rows = [["Team", "G"], ["Team A", 1.0]]

    sink.write_matchups(rows)

    worksheet = workbook.worksheets[0]
    assert worksheet.columns == [(1, 1, 25), (0, 0, 25)]
    assert worksheet.rows == [
        (0, 0, ["Team", "G"]),
        (1, 0, ["Team A", 1.0]),
    ]


def test_xlsx_sink_closes_workbook():
    sink, workbook, _ = build_sink()

    sink.close()

    assert workbook.closed is True
