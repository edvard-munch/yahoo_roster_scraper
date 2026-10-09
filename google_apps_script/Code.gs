const CONFIG_TAB = '_config';
const MENU_TITLE = 'Yahoo Roster Scraper';
const CLOUD_RUN_BACKEND = 'cloud_run';
const GITHUB_BACKEND = 'github_actions';
const GITHUB_API_ORIGIN = 'https://api.github.com';
const GITHUB_API_VERSION = '2022-11-28';
const DEFAULT_GITHUB_WORKFLOW = 'scrape-google-sheet.yml';
const DEFAULT_GITHUB_REF = 'master';
const GITHUB_PENDING_KEY = 'GITHUB_DISPATCH_PENDING';
const SEASONS = ['preseason', 'just_started', 'in_season'];
const EDITABLE_KEYS = ['league_id', 'season', 'start_date_override'];
const DISPLAY_KEYS = [...EDITABLE_KEYS, 'league_name', 'run_status',
  'run_started_at', 'last_run', 'last_error'];

function onOpen() {
  SpreadsheetApp.getUi().createMenu(MENU_TITLE)
    .addItem('Configure and run', 'showScraperSidebar')
    .addItem('Show run status', 'showRunStatus')
    .addItem('Clear pending GitHub submission', 'clearPendingGithubSubmission')
    .addToUi();
}

function showScraperSidebar() {
  const html = HtmlService.createHtmlOutputFromFile('Sidebar').setTitle(MENU_TITLE);
  SpreadsheetApp.getUi().showSidebar(html);
}

function getSidebarState() {
  const config = readConfig_(SpreadsheetApp.getActiveSpreadsheet());
  const state = {};
  DISPLAY_KEYS.forEach(key => { state[key] = config[key] || ''; });
  const pending = getPendingGithubSubmission_(config);
  state.github_dispatch_pending = Boolean(pending);
  state.github_actions_url = pending ? pending.actionsUrl : '';
  return state;
}

function showRunStatus() {
  const state = getSidebarState();
  SpreadsheetApp.getUi().alert(MENU_TITLE, statusMessage_(state),
    SpreadsheetApp.getUi().ButtonSet.OK);
}

function saveSettingsFromSidebar(values) {
  const settings = validateSettings_(values);
  return withRunLock_(() => {
    const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    assertCanStart_(readConfig_(spreadsheet));
    writeSettings_(spreadsheet, settings);
    SpreadsheetApp.flush();
    return getSidebarState();
  });
}

function runFromSidebar(values) {
  const settings = validateSettings_(values);
  const backend = getBackendSettings_();
  return withRunLock_(() => {
    const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    assertCanStart_(readConfig_(spreadsheet));
    if (backend.autoShare) {
      try {
        spreadsheet.addEditor(backend.serviceAccountEmail);
      } catch (error) {
        throw new Error('Could not share this spreadsheet with the backend service account. '
          + 'Share it manually as Editor, or ask the spreadsheet owner.');
      }
    }
    writeSettings_(spreadsheet, settings);
    SpreadsheetApp.flush();
    let result;
    if (backend.type === GITHUB_BACKEND) {
      result = dispatchGithubWorkflow_(spreadsheet, backend);
    } else {
      const request = buildScrapeRequest_(spreadsheet.getId(), backend.secret);
      let response;
      try {
        response = UrlFetchApp.fetch(backend.url + '/scrape', request);
      } catch (error) {
        // Do not expose request details or retry: the backend may still be running.
        throw new Error('Could not contact the backend. Check run status and backend logs '
          + 'before retrying; the scrape may still be running.');
      }
      result = parseBackendResponse_(response);
    }
    result.state = getSidebarState();
    return result;
  });
}

function withRunLock_(operation) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(0)) {
    throw new Error('Another scraper action is already in progress. Check run status.');
  }
  try {
    return operation();
  } finally {
    lock.releaseLock();
  }
}

function assertNotRunning_(config) {
  if (config.run_status === 'running') {
    throw new Error('A run is marked as running. Check backend logs before starting '
      + 'another run. Do not clear this status until you confirm the old run stopped.');
  }
}

function assertCanStart_(config) {
  assertNotRunning_(config);
  if (getPendingGithubSubmission_(config)) {
    throw new Error('A GitHub submission is pending. Check Actions and refresh status. '
      + 'Do not change settings or submit again while it is queued.');
  }
}

function getPendingGithubSubmission_(config) {
  const properties = PropertiesService.getScriptProperties();
  const value = properties.getProperty(GITHUB_PENDING_KEY);
  if (!value) return null;
  let pending;
  try { pending = JSON.parse(value); } catch (error) {
    throw new Error('Invalid pending GitHub submission marker. Check Actions and clear it manually.');
  }
  if (!pending || typeof pending.startedAt !== 'string'
      || typeof pending.lastRun !== 'string' || typeof pending.actionsUrl !== 'string'
      || !pending.actionsUrl.startsWith('https://github.com/')) {
    throw new Error('Invalid pending GitHub submission marker. Check Actions and clear it manually.');
  }
  if ((config.run_started_at || '') !== pending.startedAt
      || (config.last_run || '') !== pending.lastRun) {
    // Python started/completed a run since the dispatch: _config now tracks it.
    properties.deleteProperty(GITHUB_PENDING_KEY);
    return null;
  }
  return pending;
}

function clearPendingGithubSubmission() {
  const ui = SpreadsheetApp.getUi();
  const answer = ui.alert(MENU_TITLE,
    'Confirm the GitHub run failed or was cancelled BEFORE Python started, '
      + 'or that no run is queued/active. Clearing this marker does not cancel a job. '
      + 'Clear the pending submission?', ui.ButtonSet.YES_NO);
  if (answer !== ui.Button.YES) return;
  // Acquire after alert: Apps Script locks do not survive a suspended UI dialog.
  return withRunLock_(() => {
    assertNotRunning_(readConfig_(SpreadsheetApp.getActiveSpreadsheet()));
    PropertiesService.getScriptProperties().deleteProperty(GITHUB_PENDING_KEY);
  });
}

function readConfig_(spreadsheet) {
  const sheet = spreadsheet.getSheetByName(CONFIG_TAB);
  if (!sheet || sheet.getLastRow() === 0) return {};
  const config = Object.create(null);
  const rows = sheet.getRange(1, 1, sheet.getLastRow(), 2).getDisplayValues();
  rows.forEach(row => {
    const key = String(row[0] || '').trim();
    if (!key) return;
    if (Object.prototype.hasOwnProperty.call(config, key)) {
      throw new Error('Duplicate key in _config: ' + key);
    }
    config[key] = String(row[1] || '').trim();
  });
  return config;
}

function writeSettings_(spreadsheet, settings) {
  let sheet = spreadsheet.getSheetByName(CONFIG_TAB);
  if (!sheet) sheet = spreadsheet.insertSheet(CONFIG_TAB);
  const existingRows = sheet.getLastRow() === 0 ? []
    : sheet.getRange(1, 1, sheet.getLastRow(), 2).getDisplayValues();
  EDITABLE_KEYS.forEach(key => {
    const index = existingRows.findIndex(row => String(row[0]).trim() === key);
    if (index >= 0) {
      sheet.getRange(index + 1, 2).setNumberFormat('@').setValue(settings[key]);
    } else {
      const rowNumber = sheet.getLastRow() + 1;
      sheet.getRange(rowNumber, 1, 1, 2).setNumberFormat('@')
        .setValues([[key, settings[key]]]);
    }
  });
  // Preserve league_name, timestamps, run status, errors and unknown rows.
  sheet.hideSheet();
}

function validateSettings_(values) {
  if (!values || typeof values !== 'object') throw new Error('Settings are required.');
  const leagueId = String(values.league_id || '').trim();
  const season = String(values.season || '').trim();
  const startDate = String(values.start_date_override || '').trim();
  if (!/^[0-9]+$/.test(leagueId)) {
    throw new Error('League ID must contain ASCII digits.');
  }
  if (!SEASONS.includes(season)) {
    throw new Error('Choose preseason, just started, or in-season.');
  }
  if (startDate) {
    const date = new Date(startDate + 'T00:00:00Z');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(startDate)
        || startDate.startsWith('0000-')
        || Number.isNaN(date.getTime())
        || date.toISOString().slice(0, 10) !== startDate) {
      throw new Error('Schedule start date must be a valid YYYY-MM-DD date, or blank.');
    }
  }
  return {league_id: leagueId, season: season, start_date_override: startDate};
}

function getBackendSettings_() {
  const properties = PropertiesService.getScriptProperties();
  const type = (properties.getProperty('BACKEND_TYPE') || CLOUD_RUN_BACKEND).trim();
  if (![CLOUD_RUN_BACKEND, GITHUB_BACKEND].includes(type)) {
    throw new Error('BACKEND_TYPE must be cloud_run or github_actions.');
  }
  const backend = type === GITHUB_BACKEND ? getGithubSettings_(properties)
    : getCloudRunSettings_(properties);
  const autoShare = properties.getProperty('AUTO_SHARE_SERVICE_ACCOUNT') === 'true';
  const email = (properties.getProperty('SERVICE_ACCOUNT_EMAIL') || '').trim();
  if (autoShare && !/^[A-Za-z0-9._-]+@[A-Za-z0-9.-]+\.iam\.gserviceaccount\.com$/.test(email)) {
    throw new Error('Set SERVICE_ACCOUNT_EMAIL before enabling automatic sharing.');
  }
  return Object.assign(backend, {type: type, autoShare: autoShare, serviceAccountEmail: email});
}

function getCloudRunSettings_(properties) {
  const url = (properties.getProperty('BACKEND_URL') || '').trim().replace(/\/$/, '');
  const secret = properties.getProperty('BACKEND_SECRET') || '';
  if (!/^https:\/\/[A-Za-z0-9.-]+(?::443)?$/.test(url)) {
    throw new Error('Set BACKEND_URL to the backend HTTPS origin in Script Properties.');
  }
  if (!secret.trim()) throw new Error('Set BACKEND_SECRET in Script Properties.');
  return {url: url, secret: secret};
}

function getGithubSettings_(properties) {
  const repository = (properties.getProperty('GITHUB_REPOSITORY') || '').trim();
  const workflow = (properties.getProperty('GITHUB_WORKFLOW') || DEFAULT_GITHUB_WORKFLOW).trim();
  const ref = (properties.getProperty('GITHUB_REF') || DEFAULT_GITHUB_REF).trim();
  const token = properties.getProperty('GITHUB_TOKEN') || '';
  if (!/^[A-Za-z0-9][A-Za-z0-9-]*\/[A-Za-z0-9_.-]+$/.test(repository)) {
    throw new Error('Set GITHUB_REPOSITORY to owner/repository in Script Properties.');
  }
  if (!/^[A-Za-z0-9_.-]+\.ya?ml$/.test(workflow)) {
    throw new Error('GITHUB_WORKFLOW must be a workflow YAML filename.');
  }
  if (ref !== DEFAULT_GITHUB_REF) {
    throw new Error('GITHUB_REF must be master to match the trusted workflow and Google WIF policy.');
  }
  if (!token.trim()) throw new Error('Set GITHUB_TOKEN in Script Properties.');
  return {repository: repository, workflow: workflow, ref: ref, token: token};
}

function buildGithubDispatchRequest_(spreadsheetId, backend) {
  return {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer ' + backend.token,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': GITHUB_API_VERSION,
    },
    payload: JSON.stringify({ref: backend.ref, inputs: {spreadsheet_id: spreadsheetId}}),
    muteHttpExceptions: true,
    followRedirects: false,
  };
}

function dispatchGithubWorkflow_(spreadsheet, backend) {
  const config = readConfig_(spreadsheet);
  const properties = PropertiesService.getScriptProperties();
  const actionsUrl = 'https://github.com/' + backend.repository
    + '/actions/workflows/' + encodeURIComponent(backend.workflow);
  // Keep settings fixed until Python starts. Mark before sending so an ambiguous
  // network failure cannot lead to an automatic duplicate dispatch.
  properties.setProperty(GITHUB_PENDING_KEY, JSON.stringify({
    startedAt: config.run_started_at || '', lastRun: config.last_run || '',
    actionsUrl: actionsUrl,
  }));
  const url = GITHUB_API_ORIGIN + '/repos/' + backend.repository
    + '/actions/workflows/' + encodeURIComponent(backend.workflow) + '/dispatches';
  let response;
  try {
    response = UrlFetchApp.fetch(url, buildGithubDispatchRequest_(spreadsheet.getId(), backend));
  } catch (error) {
    throw new Error('GitHub submission outcome is unknown. Check Actions before retrying. '
      + 'No automatic fallback or retry was attempted.');
  }
  const code = response.getResponseCode();
  if (code === 204) {
    return {ok: true, submitted: true,
      message: 'Submitted to GitHub Actions, not completed. Wait for the job to start '
        + '(and approve it if required), then refresh status.', actionsUrl: actionsUrl};
  }
  if (code >= 300 && code < 500) properties.deleteProperty(GITHUB_PENDING_KEY);
  const messages = {
    401: 'GitHub rejected the token. Check GITHUB_TOKEN and its expiration.',
    403: 'GitHub denied dispatch or rate-limited it. Check repository Actions write permission.',
    404: 'GitHub repository/workflow was not found or is inaccessible to the token.',
    422: 'GitHub rejected dispatch. Publish the workflow on master and check its inputs.',
    429: 'GitHub rate-limited dispatch. Check Actions before retrying.',
  };
  return {ok: false, message: messages[code]
    || 'GitHub returned HTTP ' + code + '. Check Actions before clearing the pending submission.'};
}

function buildScrapeRequest_(spreadsheetId, secret) {
  return {
    method: 'post',
    contentType: 'application/json',
    headers: {Authorization: 'Bearer ' + secret},
    payload: JSON.stringify({spreadsheet_id: spreadsheetId}),
    muteHttpExceptions: true,
    followRedirects: false,
  };
}

function parseBackendResponse_(response) {
  const code = response.getResponseCode();
  let body = {};
  try { body = JSON.parse(response.getContentText()); } catch (error) { /* Not JSON. */ }
  if (!body || typeof body !== 'object') body = {};
  if (code === 200 && body.status === 'complete') {
    return {ok: true, message: 'Stats refreshed successfully.'};
  }
  const messages = {
    401: 'Backend rejected authentication. Check BACKEND_SECRET.',
    403: 'Backend access was denied. Check Cloud Run invocation permissions.',
    422: 'Request or _config is invalid. Check league, season and date settings.',
    500: 'Scraper failed. Check _config last_error and backend logs.',
    502: 'Google or Yahoo request failed. Check _config and backend logs.',
    503: 'Backend is not configured or Google credentials are unavailable.',
    504: 'Backend timed out. Check run status before retrying; it may still be running.',
  };
  return {ok: false, message: messages[code]
    || 'Backend returned HTTP ' + code + '. Check run status and logs before retrying.'};
}

function statusMessage_(state) {
  return (state.github_dispatch_pending ? 'GitHub submission pending; check Actions.\n' : '')
    + 'Status: ' + (state.run_status || 'not run')
    + '\nStarted: ' + (state.run_started_at || '-')
    + '\nLast success: ' + (state.last_run || '-')
    + '\nLast error: ' + (state.last_error || '-');
}
