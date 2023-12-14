import os
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth import exceptions


SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_FILE = 'google_credentials.json'
TOKEN_FILE = 'google_token.pickle'
API_VERSION = 'v4'
API_SERVICE_NAME = 'sheets'


def sheet_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        # if creds and creds.expired and creds.refresh_token:

        try:
            creds.refresh(Request())
        except (exceptions.RefreshError, AttributeError):
            print('REFRESH EXPIRED')

            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            print(creds)

        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    return build(API_SERVICE_NAME, API_VERSION, credentials=creds).spreadsheets()


if __name__ == '__main__':
    sheet_service()
