League has to be publicly viewable to scrape data.

## UV workflow

Install dependencies from lockfile:

```bash
uv sync
```

Run tests:

```bash
uv run --group dev pytest
```

Run lint checks:

```bash
make lint
```

Format code:

```bash
make fmt
```

Install pre-commit hooks (runs format, lint, and tests before each commit):

```bash
uv run --group dev pre-commit install
```

Run scraper:

```bash
uv run yahoo-roster-scraper
```

## Google spreadsheet lifecycle helpers

The per-league stats spreadsheet helpers require both the Google Sheets API and
Google Drive API enabled in the OAuth project's Google Cloud console. They reuse
`google_credentials.json` and `google_token.pickle`; an older token without the
`drive.file` scope will trigger browser consent once. Do not commit either file.

`league_spreadsheets.resolve_league_spreadsheet` accepts injected Sheets and Drive
clients and a `LeagueConfig`. It creates a spreadsheet named after the Yahoo league, with an empty `MATCHUPS`
tab plus a hidden `_config` tab, then reuses the tagged spreadsheet on later runs.
Drive discovery uses private app metadata, not a local registry or the file title.
Use the same Google account and OAuth client across machines for discovery.
Ambiguous matches and missing/mismatched configuration are errors, not reasons
for creating a replacement spreadsheet. The CLI stats-output integration is
planned separately; these helpers do not yet add a new interactive output option.

## Cloud Google Sheets authentication

`google_api_auth.cloud_sheet_service()` is the non-interactive authentication
factory for future cloud entrypoints. It uses Application Default Credentials
(ADC) with the Sheets scope only. The CLI continues using its existing browser
OAuth flow; it does not automatically switch to cloud authentication.

For Cloud Run:

1. Enable the Google Sheets API in the Google Cloud project.
2. Create a dedicated service account and assign it as the Cloud Run service's
   runtime identity.
3. Share each target spreadsheet with that service account's email as **Editor**.
   IAM roles alone do not grant access to a privately owned spreadsheet.
4. Let ADC use the attached identity. Do not upload `google_credentials.json`,
   `google_token.pickle`, or a downloaded service-account key into the container.

This client updates an existing spreadsheet by ID; it does not request Drive
permission or discover/create files. Missing ADC or authentication/client errors
propagate to the caller, without falling back to browser authorization.

For a local test using your own Google account rather than a service account:

```bash
gcloud auth application-default login \
  --client-id-file=google_credentials.json \
  --scopes=https://www.googleapis.com/auth/spreadsheets
```

Local ADC is separate from the scraper's OAuth token. A successful local-user ADC
test does not verify the deployed service account's spreadsheet access.
