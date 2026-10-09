# Bound Google Sheets scraper menu

This is a **container-bound** Apps Script, installed separately in each league's
spreadsheet. It is not an Apps Script web app and needs no web-app deployment.
It calls the existing synchronous Cloud Run `/scrape` endpoint; Python still runs
on the backend, never inside Google Sheets.

## Prerequisites

- Deploy the Cloud Run service using `deployment/README.md` and verify `/health`.
- For this shared-secret caller, enable Cloud Run network invocation (`allUsers`
  with `roles/run.invoker`) as described there. App-level bearer authentication
  still protects `/scrape`. This version does not issue Cloud Run IAM ID tokens.
- Share the spreadsheet with the backend's runtime service-account email as
  **Editor**, or opt in to automatic sharing below.
- Use a trusted spreadsheet: spreadsheet/script editors can inspect or modify a
  bound script and its Script Properties. Script Properties keep secrets out of
  `_config` and the sidebar, but are not a security boundary against editors.

## Install (per spreadsheet)

1. Open the target Google Sheet → **Extensions → Apps Script**.
2. Replace the default `Code.gs` contents with this directory's `Code.gs`.
3. Add an HTML file named **Sidebar** and paste `Sidebar.html` into it.
4. In **Project Settings**, enable **Show appsscript.json manifest file in editor**.
   Replace the manifest with `appsscript.json` from this directory.
5. In **Project Settings → Script Properties**, configure:

   | Property | Value |
   |---|---|
   | `BACKEND_URL` | Cloud Run HTTPS origin, e.g. `https://SERVICE.run.app` (no `/scrape` path) |
   | `BACKEND_SECRET` | Exact value of the backend's `SCRAPER_API_SECRET` |
   | `AUTO_SHARE_SERVICE_ACCOUNT` | Optional: `true` enables sharing on Run; otherwise off |
   | `SERVICE_ACCOUNT_EMAIL` | Required only for automatic sharing; e.g. `roster-scraper@PROJECT.iam.gserviceaccount.com` |

   Do not put the secret in spreadsheet cells or committed source files.
6. Save and reload the spreadsheet. The **Yahoo Roster Scraper** menu appears.
7. Choose **Configure and run**. Authorize Apps Script if prompted. This is a
   separate permission flow from the local Python OAuth app. Use an account with
   edit access; automatic sharing may require the spreadsheet owner's permission.

Permissions are limited to the bound spreadsheet, its UI, and outbound HTTPS
requests. No Drive listing or access to other spreadsheets is requested.
`Spreadsheet.addEditor` is used only when automatic sharing is explicitly enabled.
Sharing rules in your Workspace organization may still prevent that operation.

## Use the sidebar

- **League ID**: numeric Yahoo league ID.
- **Season**: preseason/offseason, just started, or in-season.
- **Schedule start date**: leave blank for today, or select tomorrow to skip today.
- **Save settings** writes only those three configuration fields; existing league
  name, timestamps, status, errors, and unknown keys remain intact.
- **Run scraper** saves settings and sends the active spreadsheet ID to `/scrape`.
  It does not send credentials or a user-selected output target: output is always
  this spreadsheet. Backend ADC selects the Google identity.
- **Refresh status** reads `_config`. **Show run status** in the menu shows the
  same information without opening the sidebar.

If `_config` does not exist, saving creates and hides it. If it already exists,
settings are updated in place. Duplicate config keys are rejected to avoid
changing a row the Python reader would ignore.

A successful run rewrites team stats and `MATCHUPS`, and synchronizes team tabs
(including removal of departed teams). The backend writes `run_started_at`,
`run_status`, `last_run`, and `last_error`. Do not use this on a spreadsheet whose
other tabs you need to retain: the tab manager treats non-reserved tabs as team
output tabs.

## Locks, timeouts, and retries

A Script Lock prevents simultaneous Save/Run actions by users of the same bound
script. A stored `run_status=running` blocks subsequent runs too. The lock is held
through the HTTP response and released in `finally` when the action finishes.
This is **not distributed locking**: CLI runs, other script projects, and backend
retries can still overlap.

This is synchronous: keep runs comfortably below the Cloud Run 300-second timeout
and Apps Script's execution limits. UrlFetch timeouts/network errors can occur
sooner. Do not automatically retry. Cloud Run can continue scraping after the
caller disconnects or receives 504. Refresh status and check backend logs first.
If a crashed run left a stale `running` status, confirm it has stopped before
manually changing that row to `failed` and starting another run. Use the planned
async job/queue version if scraping takes too long.

HTTP errors are shown as safe messages; raw backend responses and secrets are
never displayed. There is no secret/token logging in the Apps Script code.

## Test before a real run

1. Check the menu appears after reloading.
2. Confirm the sidebar loads existing league/season/date settings.
3. Save a date override; verify `_config` values changed but metadata was preserved.
4. Confirm invalid league/date input is rejected.
5. With a deliberately incorrect backend secret, Run should report authentication
   failure, without deleting stats tabs. Restore the correct secret afterward.
6. Share the spreadsheet with the runtime service account (manually or opt-in).
7. Run once and check team tabs, `MATCHUPS`, and `_config.run_status=complete`.
8. Verify a second click is blocked while a run is in progress.

Local mock tests (no Google/Cloud Run calls):

```bash
node --test tests/apps_script.test.cjs
uv run --group dev pytest -q tests/test_apps_script.py
```

Node.js 18+ is needed for the JavaScript suite; pytest skips that suite if Node is
not installed. The manifest test still runs. Live Apps Script permissions/UI and
Cloud Run egress must be tested manually after installation.
