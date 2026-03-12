import datetime
import json
import os

import google_api_auth
from environ_ import env

SPREADSHEET_ID = env('SPREADSHEET_ID')
SPREADSHEET_FILENAME_TEMPLATE = 'Leftwinglock positions_updated_at_{}'


def delete_all_sheets(service):
    """Deletes all sheets except one and clears its contents."""
    # Get the spreadsheet details, including the sheets
    response = service.get(
        spreadsheetId=SPREADSHEET_ID,
        fields='sheets.properties'
    ).execute()

    sheets = response.get('sheets', [])

    if len(sheets) < 2:
        print("No sheets found.")
        return  # No sheets to delete

    # Collect all sheet IDs
    sheet_ids = [sheet['properties']['sheetId'] for sheet in sheets]

    # Create delete requests for all sheets except the first one
    delete_requests = [{'deleteSheet': {'sheetId': sheet_id}} for sheet_id in sheet_ids[1:]]

    # Perform the batchUpdate to delete the sheets
    service.batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={'requests': delete_requests}
    ).execute()

    print("All sheets except one have been deleted.")


def sheet_exists(sheets, sheet_title):
    """Check if a sheet with the given title already exists."""
    for sheet in sheets:
        if sheet['properties']['title'] == sheet_title:
            return True  # The sheet already exists
    return False  # The sheet doesn't exist


def google(filename):
    service = google_api_auth.sheet_service()
    print("Service type:", type(service))

    delete_all_sheets(service)

    sheets = service.get(spreadsheetId=SPREADSHEET_ID,
                         fields='sheets.properties.title').execute()['sheets']
    print(sheets)
    with open(filename) as text_file:
        json_load_data = json.load(text_file)

        for key, value in json_load_data.items():
            key = key.strip()
            print(key)
            number_of_seasons = 0
            vals_to_sheet = [['Name'], ['']]
            index = 2

            for el in value:
                vals_to_sheet.append([])
                vals_to_sheet[index].append(el['name'])
                for season in el['seasons']:
                    if season['Season'] not in vals_to_sheet[0]:
                        number_of_seasons += 1
                        vals_to_sheet[0].extend([season['Season'], '', '', ''])
                        vals_to_sheet[1].extend(
                            ['Team', 'Left', 'Center', 'Right'])

                    vals_to_sheet[index].extend([
                        season['Team'], season['Left'], season['Center'],
                        season['Right']
                    ])

                index += 1

            if not sheet_exists(sheets, key):
                add_sheet(service, key)

            service.values().update(spreadsheetId=SPREADSHEET_ID,
                                    range=key,
                                    valueInputOption='RAW',
                                    body=dict(values=vals_to_sheet)).execute()

    sheets = service.get(spreadsheetId=SPREADSHEET_ID,
                         fields='sheets.properties').execute()['sheets']

    date = get_modification_date(filename)
    rename_spreadsheet(service, SPREADSHEET_FILENAME_TEMPLATE.format(date))

    handle_merging(service, sheets, number_of_seasons)
    handle_frozen_row(service, sheets)


def rename_spreadsheet(service, new_title):
    request_body = {
        'requests': [{
            'updateSpreadsheetProperties': {
                'properties': {
                    'title': new_title,
                },
                'fields': 'title',
            }
        }]
    }

    service.batchUpdate(spreadsheetId=SPREADSHEET_ID,
                        body=request_body).execute()


def handle_merging(service, sheets, number_of_seasons):
    requests = []
    for sheet in sheets:
        sheet_id = sheet['properties']['sheetId']
        requests.append(compose_request_body(sheet_id, [0, 2, 0, 1], "MERGE_COLUMNS"))

        # seasons
        one_season_columns_span = 4
        start_row, end_row = 0, 1
        start_column, end_column = 1, 5

        for i in range(number_of_seasons):
            indexes = [
              start_row, end_row, start_column + (i * one_season_columns_span),
              end_column + (i * one_season_columns_span)
            ]
            requests.append(compose_request_body(sheet_id, indexes, "MERGE_ROWS"))

    merge_cells(service, requests)


def compose_request_body(sheet_id, indexes, merge_type):
    return {
        "mergeCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": indexes[0],
                "endRowIndex": indexes[1],
                "startColumnIndex": indexes[2],
                "endColumnIndex": indexes[3],
            },
            "mergeType": merge_type
        }
    }


def merge_cells(service, requests):
    print('MERGING')

    request_body = {
        'requests': requests
    }

    service.batchUpdate(spreadsheetId=SPREADSHEET_ID,
                        body=request_body).execute()
    print('MERGED')


def get_modification_date(file):
    epoch_time = os.path.getmtime(file)
    return datetime.date.fromtimestamp(epoch_time)


def handle_frozen_row(service, sheets):
    print('FROZING')
    for sheet in sheets:
        sheet_id = sheet['properties']['sheetId']
        print(sheet_id)

        name_column_index = 0

        # Define the fixed width you want for the "Name" column (in pixels).
        fixed_column_width = 150  # Example: set the width to 200 pixels

        # Set the fixed column width for the "Name" column
        set_fixed_column_width(service, sheet_id, name_column_index, fixed_column_width)

        request_body = {
            "requests": [{
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 2
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {
                                "red": 0.0,
                                "green": 0.0,
                                "blue": 0.0
                            },
                            "horizontalAlignment": "CENTER",
                            "verticalAlignment": "MIDDLE",
                            "textFormat": {
                                "foregroundColor": {
                                    "red": 1.0,
                                    "green": 1.0,
                                    "blue": 1.0
                                },
                                "fontSize": 12,
                                "bold": True
                            }
                        }
                    },
                    "fields":
                    "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)"
                }
            }, {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {
                            "frozenRowCount": 2
                        }
                    },
                    "fields": "gridProperties.frozenRowCount"
                }
            }]
        }
        service.batchUpdate(spreadsheetId=SPREADSHEET_ID,
                            body=request_body).execute()
    print('FROZEN')    


def set_fixed_column_width(service, sheet_id, column_index, width):
    """Sets a fixed width for a specific column in the given sheet."""
    print(sheet_id)
    request_body = {
        "requests": [{
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": column_index,
                    "endIndex": column_index + 1
                },

                "properties": {
                    "pixelSize": width  # Set the fixed width here
                },

                "fields": "pixelSize"  # This tells the API to update the pixel size
            }
        }]
    }

    try:
        response = service.batchUpdate(spreadsheetId=SPREADSHEET_ID, body=request_body).execute()
        print(f"Column {column_index} width set to {width} pixels.")
    except google_api_auth.HttpError as err:
        print(f"Failed to update column width: {err}")


def unmerge_cells(service, sheet_id):
    request_body = {
        'requests': [{
            "unmergeCells": {
                "range": {
                    "sheetId": sheet_id,
                },
            }
        }]
    }

    service.batchUpdate(spreadsheetId=SPREADSHEET_ID,
                        body=request_body).execute()


def add_sheet(service, title):
    request_body = {
        'requests': [{
            'addSheet': {
                'properties': {
                    'title': title
                },
            }
        }]
    }

    service.batchUpdate(spreadsheetId=SPREADSHEET_ID,
                        body=request_body).execute()
