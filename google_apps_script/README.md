# Bound Google Sheets scraper menu

This is a **container-bound** Apps Script, installed separately in each league's
spreadsheet. It is not an Apps Script web app and needs no web-app deployment.
It can call the synchronous Cloud Run `/scrape` endpoint or asynchronously dispatch
a GitHub Actions workflow. Python runs on the selected backend, never inside
Google Sheets. Set `BACKEND_TYPE` in Script Properties to select the provider;
missing `BACKEND_TYPE` retains the existing Cloud Run behavior.

## Prerequisites

- **Cloud Run mode:** deploy using `deployment/README.md` and verify `/health`.
- **GitHub mode:** publish/configure the workflow using
  `deployment/GITHUB_ACTIONS.md`. No Cloud Run service or backend secret is required.
- For the Cloud Run shared-secret caller, enable network invocation (`allUsers`
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
   | `BACKEND_TYPE` | `cloud_run` (default) or `github_actions` |
   | `BACKEND_URL` | Cloud Run only: HTTPS origin, e.g. `https://SERVICE.run.app` (no `/scrape` path) |
   | `BACKEND_SECRET` | Cloud Run only: exact value of `SCRAPER_API_SECRET` |
   | `GITHUB_REPOSITORY` | GitHub only: `edvard-munch/yahoo_roster_scraper` |
   | `GITHUB_TOKEN` | GitHub only: fine-grained token with Actions write on that repository |
   | `GITHUB_WORKFLOW` | Optional: defaults to `scrape-google-sheet.yml` |
   | `GITHUB_REF` | Optional: defaults to `master`; other branches are rejected |
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
- **Run scraper** saves settings and sends the active spreadsheet ID to the
  selected provider. No league/config values or Google credentials are included
  in the payload; authorization credentials are sent only in the HTTPS header.
  Output is always this spreadsheet. Backend ADC selects the Google identity.
- Cloud Run waits for completion. GitHub returns **submitted, not completed**;
  use **Open GitHub Actions** to inspect the run/approve it if required, then
  **Refresh status** after Python starts.
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
In GitHub mode that response acknowledges dispatch, not scraper completion.
This is **not distributed locking**: CLI runs, other script projects, and backend
retries can still overlap.

The Cloud Run path is synchronous: keep runs comfortably below the 300-second
Cloud Run timeout and Apps Script's execution limits. UrlFetch timeouts/network errors can occur
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
5. With a deliberately incorrect provider credential (Cloud Run secret or GitHub
   token), Run should report authentication failure without deleting stats tabs.
   Restore the correct credential afterward.
6. Share the spreadsheet with the runtime service account (manually or opt-in).
7. Run once and check team tabs, `MATCHUPS`, and `_config.run_status=complete`.
8. Verify a second click is blocked while running or while GitHub is pending.

Local mock tests (no Google/Cloud Run calls):

```bash
node --test tests/apps_script.test.cjs
uv run --group dev pytest -q tests/test_apps_script.py
```

Node.js 18+ is needed for the JavaScript suite; pytest skips that suite if Node is
not installed. The manifest test still runs. Live Apps Script permissions/UI and
selected backend's egress must be tested manually after installation.


## GitHub token and submission setup

First complete `deployment/GITHUB_ACTIONS.md`: the workflow must exist on `master`,
its `google-sheets` environment must have WIF settings, and the Google service
account must be an Editor on this spreadsheet. The GitHub token below does **not**
grant Google access; identity federation does that separately.

In GitHub: **Settings → Developer settings → Personal access tokens → Fine-grained
tokens → Generate new token**. Choose the repository's resource owner, select
**Only select repositories → yahoo_roster_scraper**, and grant **Repository
permissions → Actions: Read and write**. Use an expiration and rotate the token.
Organization-owned repositories may require token approval. Do not grant broad
classic-token scopes merely to get dispatch working.

Copy the token into `GITHUB_TOKEN` in Apps Script's Script Properties. Set
`BACKEND_TYPE=github_actions` and `GITHUB_REPOSITORY=edvard-munch/yahoo_roster_scraper`.
The workflow/ref defaults match the checked-in workflow and Google trust policy.
Updating the default branch requires coordinated changes to the workflow, WIF
policy, and this script's allowed ref—not just setting an arbitrary branch here.

You can keep Cloud Run's properties alongside GitHub's and switch explicitly by
changing `BACKEND_TYPE`. There is no automatic fallback, because falling back
could submit the same scrape twice. If using automatic sharing, make
`SERVICE_ACCOUNT_EMAIL` match the selected backend identity; otherwise manually
share the spreadsheet with both Google service accounts.

## Pending GitHub submissions

GitHub acknowledges with HTTP 204; it does not return completion or a run ID for
this request. The link opens that workflow's run history. Approval waits, queue
waits, setup errors, or failed WIF authentication happen **before** Python starts
and do not change `_config`. The sheet can therefore still show the previous
successful run's status/timestamp after a dispatch.

A non-secret `GITHUB_DISPATCH_PENDING` marker in Script Properties records the
previous run timestamps. While pending, Save/Run are disabled and rejected on the
server so a queued job does not read settings changed after dispatch. The marker
clears when a refreshed `_config` indicates Python has started/completed a newer
run. It does not claim to be an authoritative GitHub job status or distributed
lock; avoid simultaneous CLI/Cloud Run runs on the same spreadsheet.

Network errors and 5xx responses leave the outcome **unknown**; the pending guard
remains, with no retry/fallback. A clear 4xx dispatch rejection removes it. To
recover after a job was cancelled/failed before Python started, or after checking
that an unknown submission never arrived, use **Clear pending GitHub submission**
in the menu and confirm only after inspecting Actions. Clearing does not cancel
anything. A `running` Python status cannot be cleared through this menu; confirm
it stopped before manually repairing a stale `_config` status.

The workflow serializes active runs for the same spreadsheet within this
repository. GitHub may replace an older pending run with a newer dispatch, so
repeated submission is not a queue you should rely on. Cancellation/timeouts can
still leave stale state. This version neither polls GitHub nor automatically
retries jobs. No new Apps Script OAuth scopes are needed for GitHub dispatch.
