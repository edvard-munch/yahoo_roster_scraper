import hmac
import logging
import os
from typing import Annotated

import requests
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError
from pydantic import BaseModel, ConfigDict, Field

from . import runtime
from .services import google_api_auth, google_sheet_runner, sheet_run_config


API_SECRET_ENV = "SCRAPER_API_SECRET"
SPREADSHEET_ID_PATTERN = r"^[A-Za-z0-9_-]+$"
MAX_SPREADSHEET_ID_LENGTH = 256
BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}
logger = logging.getLogger(__name__)
bearer_auth = HTTPBearer(auto_error=False)


class ScrapeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    spreadsheet_id: str = Field(
        min_length=1,
        max_length=MAX_SPREADSHEET_ID_LENGTH,
        pattern=SPREADSHEET_ID_PATTERN,
    )


def authenticate(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_auth)],
):
    secret = os.environ.get(API_SECRET_ENV)
    if not secret or not secret.strip():
        raise HTTPException(status_code=503, detail="Scraper endpoint is not configured")
    if credentials is None or not hmac.compare_digest(
        credentials.credentials.encode("utf-8"), secret.encode("utf-8")
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing bearer token",
            headers=BEARER_CHALLENGE,
        )


def run_scraper(spreadsheet_id):
    # Clients are per request: googleapiclient transports are not thread-safe.
    sheets_service = google_api_auth.cloud_sheet_service()
    scrape_dependencies, matchups_context = runtime.build_default_sheet_runtime()
    return google_sheet_runner.run_google_sheet_scrape(
        sheets_service,
        spreadsheet_id,
        scrape_dependencies,
        matchups_context,
    )


def get_scrape_runner():
    return run_scraper


def create_app():
    app = FastAPI(title="Yahoo Roster Scraper")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/scrape", dependencies=[Depends(authenticate)])
    def scrape(payload: ScrapeRequest, runner=Depends(get_scrape_runner)):
        try:
            runner(payload.spreadsheet_id)
        except sheet_run_config.SheetConfigError as error:
            # Validation messages do not include the rejected config values.
            raise HTTPException(status_code=422, detail=str(error)) from error
        except google_sheet_runner.LeaguePreparationError as error:
            raise HTTPException(
                status_code=502, detail="Could not prepare the Yahoo league"
            ) from error
        except GoogleAuthError as error:
            logger.error("Cloud Google authentication failed (%s)", type(error).__name__)
            raise HTTPException(
                status_code=503, detail="Google authentication unavailable"
            ) from error
        except HttpError as error:
            logger.error("Google Sheets request failed (%s)", getattr(error.resp, "status", None))
            raise HTTPException(status_code=502, detail="Google Sheets request failed") from error
        except requests.RequestException as error:
            logger.error("Upstream scraper request failed (%s)", type(error).__name__)
            raise HTTPException(
                status_code=502, detail="Upstream scraper request failed"
            ) from error
        except Exception as error:
            logger.error("Scraper run failed (%s)", type(error).__name__)
            raise HTTPException(status_code=500, detail="Scraper run failed") from error

        return {"status": "complete", "spreadsheet_id": payload.spreadsheet_id}

    return app


app = create_app()
