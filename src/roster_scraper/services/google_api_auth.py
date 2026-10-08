import os
import pickle

import google.auth
from google.auth import exceptions
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]
CLOUD_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_FILE = "google_credentials.json"
TOKEN_FILE = "google_token.pickle"
API_VERSION = "v4"
API_SERVICE_NAME = "sheets"
DRIVE_API_SERVICE_NAME = "drive"
DRIVE_API_VERSION = "v3"


def get_credentials():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid or not creds.has_scopes(SCOPES):
        try:
            if creds and not creds.has_scopes(SCOPES):
                raise exceptions.RefreshError("Additional Google permissions require consent")
            creds.refresh(Request())
        except (exceptions.RefreshError, AttributeError):
            print("REFRESH EXPIRED")

            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    return creds


def sheet_service():
    return build(API_SERVICE_NAME, API_VERSION, credentials=get_credentials()).spreadsheets()


def cloud_sheet_service():
    """Build a Sheets client using ADC, without installed-app OAuth or token files."""
    credentials, _ = google.auth.default(scopes=CLOUD_SCOPES)
    return build(API_SERVICE_NAME, API_VERSION, credentials=credentials).spreadsheets()


def drive_service():
    return build(DRIVE_API_SERVICE_NAME, DRIVE_API_VERSION, credentials=get_credentials()).files()


if __name__ == "__main__":
    sheet_service()
