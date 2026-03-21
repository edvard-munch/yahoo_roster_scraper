import datetime
from types import SimpleNamespace

from roster_scraper.core import output


class WorksheetSpy:
    def __init__(self):
        self.set_column_calls = []
        self.write_calls = []
        self.write_column_calls = []

    def set_column(self, *args):
        self.set_column_calls.append(args)

    def write(self, row, col, value):
        self.write_calls.append((row, col, value))

    def write_column(self, row, col, values):
        self.write_column_calls.append((row, col, list(values)))


def test_verify_sheet_name_removes_invalid_excel_characters():
    assert output.verify_sheet_name("BOS/ANA*MTL") == "BOSANAMTL"


def test_get_filename_uses_timestamp_template(monkeypatch):
    real_datetime = datetime.datetime
    fixed_now = datetime.datetime(2024, 1, 2, 3, 4, 5)

    class DummyDatetime:
        @staticmethod
        def now():
            return fixed_now

        @staticmethod
        def strftime(value, fmt):
            return real_datetime.strftime(value, fmt)

    monkeypatch.setattr(output.datetime, "datetime", DummyDatetime)

    filename = output.get_filename()

    assert filename == "reports/stats_list_20240102-030405.xlsx"


def test_write_to_xlsx_writes_headers_and_columns():
    worksheet = WorksheetSpy()
    table = {
        "Team": ["BOS", "MTL"],
        "G": [1, 2],
    }

    output.write_to_xlsx(table, worksheet)

    assert worksheet.set_column_calls == [(1, 1, output.WIDE_COLUMN_WIDTH)]
    assert worksheet.write_calls == [(0, 0, "Team"), (0, 1, "G")]
    assert worksheet.write_column_calls == [
        (1, 0, ["BOS", "MTL"]),
        (1, 1, [1, 2]),
    ]


def test_write_roster_to_txt_filters_empty_spots(tmp_path, monkeypatch):
    output_file = tmp_path / "clean_rosters.txt"
    monkeypatch.setattr(output, "TXT_FILENAME", str(output_file))

    output.write_roster_to_txt(
        full_roster=[["Player One", "Empty", "Player Two"]],
        file_mode="w",
        team_name="Team One",
        empty_spot_string="Empty",
    )

    text = output_file.read_text()

    assert "Player One" in text
    assert "Player Two" in text
    assert "Empty" not in text


def test_open_file_uses_startfile_on_windows(monkeypatch):
    calls = []
    monkeypatch.setattr(output.sys, "platform", output.PLATFORMS["Windows"])
    monkeypatch.setattr(
        output.os, "startfile", lambda filename: calls.append(filename), raising=False
    )

    output.open_file("report.xlsx")

    assert calls == ["report.xlsx"]


def test_open_file_uses_subprocess_on_linux(monkeypatch):
    calls = []
    monkeypatch.setattr(output.sys, "platform", "linux")
    monkeypatch.setattr(output.subprocess, "call", lambda args: calls.append(args))

    output.open_file("report.xlsx")

    assert calls == [[output.FILE_OPENERS["Linux"], "report.xlsx"]]
