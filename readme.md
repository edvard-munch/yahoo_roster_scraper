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

## Authenticated HTTP scraper endpoint

The synchronous FastAPI service provides:

- `GET /health`: public liveness check, with no scraping or Google authorization.
- `POST /scrape`: accepts only `{"spreadsheet_id": "<spreadsheet ID>"}` and reads
  league/season/date settings from that spreadsheet's `_config` tab.

After installing dependencies (`uv sync --group dev`), start it locally:

```bash
export SCRAPER_API_SECRET="$(openssl rand -hex 32)"
uv run uvicorn roster_scraper.web:app --host 127.0.0.1 --port 8080
```

Keep the secret in your environment (Secret Manager when deployed), not in source
code or the spreadsheet. Clients must send `Authorization: Bearer <secret>`.
Anyone holding this secret can request runs against spreadsheets accessible to the
backend identity, so restrict who can read it and rotate it if exposed.

For example, from another terminal with the same secret configured:

```bash
curl http://127.0.0.1:8080/health
curl -X POST http://127.0.0.1:8080/scrape \
  -H "Authorization: Bearer $SCRAPER_API_SECRET" \
  -H 'Content-Type: application/json' \
  -d '{"spreadsheet_id":"YOUR_SPREADSHEET_ID"}'
```

**A successful POST performs a real refresh:** it clears/rewrites stats values and
synchronizes team tabs. The response arrives after the run finishes. This endpoint
uses `cloud_sheet_service()` (ADC); it never launches installed-app OAuth. Share
that spreadsheet with the runtime service account as Editor, or configure local
ADC as described above for testing. No Drive lookup or spreadsheet creation is
performed by this endpoint.

Responses: `200` complete, `401` missing/invalid bearer token, `422` malformed
request or invalid `_config`, `502` league/upstream API failure, `503` missing
server secret or unavailable Google credentials, `500` unexpected scraper failure.
Upstream error bodies and bearer tokens are not returned or logged by the HTTP
handler. Run details remain in `_config` and existing scraper logs.

The HTTP layer creates Google clients per request. Its default runtime adapter
reuses existing Yahoo parsing helpers without executing CLI prompts. Keep the
existing `uv run yahoo-roster-scraper` command for interactive local runs.
Apps Script integration and distributed run locking are separate steps. Avoid overlapping runs against the same spreadsheet in this
synchronous version; use a single worker/concurrency of one when deploying it.

## Cloud Run packaging

The HTTP service can be built with `docker build -t yahoo-roster-scraper:cloud-run .`.
The container runs as a non-root user and requires `SCRAPER_API_SECRET` at startup;
its launcher uses Cloud Run's `PORT` and one Uvicorn worker. Local CLI usage is
unchanged. See [deployment instructions](deployment/README.md) for Secret Manager,
service-account spreadsheet access, the Cloud Run template, and smoke tests.

## Run from a Google Sheet

Install the container-bound menu/sidebar using
[the Apps Script instructions](google_apps_script/README.md). It edits the bound
spreadsheet's `_config` and calls the Cloud Run endpoint with a bearer secret from
Script Properties. The interactive Python CLI remains available and unchanged.
