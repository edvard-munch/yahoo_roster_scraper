import re

from roster_scraper.core.constants import (
    COLUMNS_TO_DELETE,
    EMPTY_SPOT_STRING,
    EMPTY_STRING_PATTERN,
    PLAYER_LINK_CLASSES,
    PLAYER_NAME_CLASS,
    POSITION_CODES,
    SCORING_COLUMNS,
    TEAM_AND_POSITION_SPAN_CLASS,
)
from roster_scraper.services import positions as positions_scraper


def string_to_num(value, delimeter):
    if value is None:
        return 0.0

    text = str(value)
    if delimeter is not None:
        text = text.split(delimeter)[0]

    text = re.sub(EMPTY_STRING_PATTERN, "0", text).strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return 0.0

    return float(match.group(0))


def calculate_totals(column_values, games_per_week):
    total = 0

    for index, value in enumerate(column_values):
        total += string_to_num(value, None) * games_per_week[index]

    return total


def map_headers_to_body(headers, body, season_in_progress):
    headers_keys = headers.copy().keys()
    games_per_week_column = body[-1]

    for index, key in enumerate(headers_keys):
        headers[key] = body[index]

        if season_in_progress and (key in SCORING_COLUMNS):
            headers[key].append(calculate_totals(headers[key], games_per_week_column))

        if key in COLUMNS_TO_DELETE:
            headers.pop(key, None)

    return headers


def parse_for_json(skaters):
    rows = skaters.find_all("tr")
    roster = []

    for row in rows:
        for cell in row:
            if PLAYER_NAME_CLASS in cell.attrs["class"]:
                player_link = cell.find(class_=PLAYER_LINK_CLASSES)

                if player_link:
                    name = player_link.string
                    span = cell.find(lambda tag: tag.get("class") == [TEAM_AND_POSITION_SPAN_CLASS])
                    position = span.string.split(" - ")[1]

                    if position != POSITION_CODES[1]:
                        pos_data = positions_scraper.get_positional_data([], name)
                        roster.append(pos_data)
    return roster


def parse_clean_names(bodies):
    full_roster = []
    for body in bodies:
        rows = body.find_all("tr")

        txt = []
        for row_index, row in enumerate(rows):
            rostered_found = False
            for cell in row:
                if PLAYER_NAME_CLASS in cell.attrs["class"]:
                    player_link = cell.find(class_=PLAYER_LINK_CLASSES)
                    txt.append([])

                    if player_link:
                        txt[row_index].append(player_link.string)
                    else:
                        txt[row_index].append(EMPTY_SPOT_STRING)

                cell_text = cell.get_text(strip=True)
                if (not rostered_found) and ("%" in cell_text):
                    txt[row_index].append(cell_text)
                    rostered_found = True

            if txt[row_index] and len(txt[row_index]) == 1:
                txt[row_index].append("0%")

        res = sorted(txt, key=lambda x: string_to_num(x[1], "%"), reverse=True)
        zipped = list(zip(*res))
        full_roster.append(zipped[0])

    return full_roster
