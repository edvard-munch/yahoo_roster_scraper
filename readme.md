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
