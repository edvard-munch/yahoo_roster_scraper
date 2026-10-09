"""Non-interactive spreadsheet scraper command for Actions and other job runners."""

import argparse
import re
import sys

from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError

from . import runtime
from .services import google_api_auth, google_sheet_runner, sheet_run_config


SPREADSHEET_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,256}")
COMMAND_NAME = "yahoo-roster-scraper-actions"
EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def parse_spreadsheet_id(value):
    if not SPREADSHEET_ID_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "Supply a spreadsheet ID (1–256 letters, digits, underscores or hyphens), not a URL"
        )
    return value


def run_actions_scrape(spreadsheet_id):
    sheets_service = google_api_auth.cloud_sheet_service()
    dependencies, matchups_context = runtime.build_default_sheet_runtime()
    google_sheet_runner.run_google_sheet_scrape(
        sheets_service,
        spreadsheet_id,
        dependencies,
        matchups_context,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog=COMMAND_NAME,
        description="Refresh stats in an existing Google spreadsheet using ADC and _config.",
    )
    parser.add_argument("--spreadsheet-id", required=True, type=parse_spreadsheet_id)
    args = parser.parse_args(argv)

    try:
        run_actions_scrape(args.spreadsheet_id)
    except GoogleAuthError:
        print("Google ADC authentication failed. Check the runner's credentials.", file=sys.stderr)
        return EXIT_FAILURE
    except HttpError:
        print(
            "Google Sheets request failed. Check API setup and spreadsheet access.", file=sys.stderr
        )
        return EXIT_FAILURE
    except sheet_run_config.SheetConfigError:
        print(
            "Invalid _config. Check league ID, season and schedule date settings.", file=sys.stderr
        )
        return EXIT_FAILURE
    except google_sheet_runner.LeaguePreparationError:
        print(
            "Could not prepare the Yahoo league. Check league visibility and connectivity.",
            file=sys.stderr,
        )
        return EXIT_FAILURE
    except Exception:
        # Upstream exceptions/tracebacks can contain credentials or request details.
        print("Scraper run failed. Check _config run_status and last_error.", file=sys.stderr)
        return EXIT_FAILURE

    print(f"Stats refresh complete for spreadsheet {args.spreadsheet_id}.")
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
