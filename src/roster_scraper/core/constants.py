import num2words


TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"
XLSX_FILENAME_TEMPLATE = "reports/stats_list_{}.xlsx"
TXT_FILENAME = "reports/clean_rosters.txt"
TEAM_NAME_HEADER = "--------------- {} ---------------"

INVALID_EXCEL_CHARACTERS_PATTERN = r"[*\\\/]"
EMPTY_STRING_PATTERN = r"^-$"

PLATFORMS = {
    "Windows": "win32",
    "Mac_OS": "darwin",
}

FILE_OPENERS = {"Linux": "xdg-open", "Mac_OS": "open"}

NUMBER_OF_COLUMNS = 15
WIDE_COLUMN_WIDTH = 20
COLUMNS = {
    num2words.num2words(i + 1, to="ordinal"): (i, i)
    for i in range(NUMBER_OF_COLUMNS)
}

SCORING_COLUMNS = [
    "G", "A", "P", "+/-", "PIM", "PPP", "PPG", "PPA", "SHP", "GWG", "SOG", "FW", "HIT", "BLK",
]

COLUMNS_TO_DELETE = [
    "Action", "Add", "Opp", "Status", "Pre-Season", "Current", "% Started"
]

EMPTY_SPOT_STRING = "Empty"
PLAYER_NAME_CLASS = "player"
PLAYER_LINK_CLASSES = "Nowrap name F-link playernote"
TEAM_AND_POSITION_SPAN_CLASS = "Fz-xxs"
POSITION_CODES = ["G", "D", "LW", "RW", "C"]
