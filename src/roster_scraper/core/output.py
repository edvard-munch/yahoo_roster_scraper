import datetime
import os
import re
import subprocess
import sys

from roster_scraper.core.constants import (
    COLUMNS,
    FILE_OPENERS,
    INVALID_EXCEL_CHARACTERS_PATTERN,
    PLATFORMS,
    TEAM_NAME_HEADER,
    TIMESTAMP_FORMAT,
    TXT_FILENAME,
    WIDE_COLUMN_WIDTH,
    XLSX_FILENAME_TEMPLATE,
)


def get_filename():
    now = datetime.datetime.now()
    timestamp = datetime.datetime.strftime(now, TIMESTAMP_FORMAT)
    return XLSX_FILENAME_TEMPLATE.format(timestamp)


def open_file(filename):
    if sys.platform == PLATFORMS['Windows']:
        os.startfile(filename)
    else:
        if sys.platform == PLATFORMS['Mac_OS']:
            opener = FILE_OPENERS['Mac_OS']
        else:
            opener = FILE_OPENERS['Linux']

        subprocess.call([opener, filename])


def verify_sheet_name(team_name):
    return re.sub(INVALID_EXCEL_CHARACTERS_PATTERN, '', team_name)


def write_to_xlsx(table, worksheet):
    col_num = 0
    worksheet.set_column(*COLUMNS['second'], WIDE_COLUMN_WIDTH)

    for key, value in table.items():
        worksheet.write(0, col_num, key)
        worksheet.write_column(1, col_num, value)
        col_num += 1


def write_roster_to_txt(full_roster, file_mode, team_name, empty_spot_string):
    with open(TXT_FILENAME, file_mode) as text_file:
        text_file.write(TEAM_NAME_HEADER.format(team_name))
        text_file.write('\n\n')

        for roster in full_roster:
            text_file.write("\n".join(
                str(item) for item in roster if item != empty_spot_string))
            text_file.write('\n\n')

        text_file.write('\n')
