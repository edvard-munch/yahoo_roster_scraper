const CONFIG_TAB = '_config';
const MENU_TITLE = 'Yahoo Roster Scraper';
const SEASONS = ['preseason', 'just_started', 'in_season'];
const EDITABLE_KEYS = ['league_id', 'season', 'start_date_override'];
const DISPLAY_KEYS = [...EDITABLE_KEYS, 'league_name', 'run_status',
  'run_started_at', 'last_run', 'last_error'];

function onOpen() {
  SpreadsheetApp.getUi().createMenu(MENU_TITLE)
    .addItem('Configure and run', 'showScraperSidebar')
    .addItem('Show run status', 'showRunStatus')
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
    assertNotRunning_(readConfig_(spreadsheet));
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
    assertNotRunning_(readConfig_(spreadsheet));
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
    const request = buildScrapeRequest_(spreadsheet.getId(), backend.secret);
    let response;
    try {
      response = UrlFetchApp.fetch(backend.url + '/scrape', request);
    } catch (error) {
      // Do not expose request details or retry: the backend may still be running.
      throw new Error('Could not contact the backend. Check run status and backend logs '
        + 'before retrying; the scrape may still be running.');
    }
    const result = parseBackendResponse_(response);
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
  const url = (properties.getProperty('BACKEND_URL') || '').trim().replace(/\/$/, '');
  const secret = properties.getProperty('BACKEND_SECRET') || '';
  if (!/^https:\/\/[A-Za-z0-9.-]+(?::443)?$/.test(url)) {
    throw new Error('Set BACKEND_URL to the backend HTTPS origin in Script Properties.');
  }
  if (!secret.trim()) throw new Error('Set BACKEND_SECRET in Script Properties.');
  const autoShare = properties.getProperty('AUTO_SHARE_SERVICE_ACCOUNT') === 'true';
  const email = (properties.getProperty('SERVICE_ACCOUNT_EMAIL') || '').trim();
  if (autoShare && !/^[A-Za-z0-9._-]+@[A-Za-z0-9.-]+\.iam\.gserviceaccount\.com$/.test(email)) {
    throw new Error('Set SERVICE_ACCOUNT_EMAIL before enabling automatic sharing.');
  }
  return {url: url, secret: secret, autoShare: autoShare, serviceAccountEmail: email};
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
  return 'Status: ' + (state.run_status || 'not run')
    + '\nStarted: ' + (state.run_started_at || '-')
    + '\nLast success: ' + (state.last_run || '-')
    + '\nLast error: ' + (state.last_error || '-');
}
