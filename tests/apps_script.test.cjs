const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../google_apps_script/Code.gs'), 'utf8');
const plain = value => JSON.parse(JSON.stringify(value));

function fixture(rows = []) {
  const events = [];
  let storedRows = rows.map(row => [...row]);
  let present = true;
  let allowedLock = true;
  const properties = {BACKEND_URL: 'https://example.run.app', BACKEND_SECRET: 'private-secret'};
  const sheet = {
    getLastRow: () => storedRows.length,
    hideSheet: () => events.push('hide'),
    getRange: (row, column, count = 1, width = 1) => {
      const range = {
        getDisplayValues: () => Array.from({length: count}, (_, offset) =>
          Array.from({length: width}, (_, colOffset) =>
            String((storedRows[row - 1 + offset] || [])[column - 1 + colOffset] || ''))),
        setNumberFormat: () => range,
        setValue: value => {
          storedRows[row - 1] ||= [];
          storedRows[row - 1][column - 1] = value;
          return range;
        },
        setValues: values => {
          values.forEach((valuesRow, offset) => {
            storedRows[row - 1 + offset] ||= [];
            valuesRow.forEach((value, colOffset) => {
              storedRows[row - 1 + offset][column - 1 + colOffset] = value;
            });
          });
          return range;
        },
      };
      return range;
    },
  };
  const spreadsheet = {
    getId: () => 'sheet-123',
    getSpreadsheetTimeZone: () => 'Europe/Moscow',
    getSheetByName: () => present ? sheet : null,
    insertSheet: title => { events.push(['insert', title]); present = true; return sheet; },
    addEditor: email => events.push(['share', email]),
  };
  const menu = {
    addItem: (name, callback) => { events.push(['menu', name, callback]); return menu; },
    addToUi: () => events.push('menu-added'),
  };
  const ui = {
    createMenu: () => menu,
    showSidebar: () => events.push('sidebar'),
    alert: (...args) => events.push(['alert', ...args]),
    ButtonSet: {OK: 'OK', YES_NO: 'YES_NO'},
    Button: {YES: 'YES'},
  };
  const context = vm.createContext({
    SpreadsheetApp: {
      getActiveSpreadsheet: () => spreadsheet,
      getUi: () => ui,
      flush: () => events.push('flush'),
    },
    PropertiesService: {getScriptProperties: () => ({
      getProperty: key => properties[key],
      setProperty: (key, value) => { properties[key] = value; },
      deleteProperty: key => { delete properties[key]; },
    })},
    LockService: {getScriptLock: () => ({
      tryLock: timeout => { events.push(['lock', timeout]); return allowedLock; },
      releaseLock: () => events.push('release'),
    })},
    UrlFetchApp: {fetch: (url, options) => {
      events.push(['fetch', url, options]);
      return {getResponseCode: () => 200, getContentText: () => '{"status":"complete"}'};
    }},
    HtmlService: {createHtmlOutputFromFile: () => ({setTitle: () => ({})})},
  });
  vm.runInContext(source, context);
  return {
    context, events, properties, spreadsheet,
    rows: () => storedRows,
    lock: value => { allowedLock = value; },
    missing: () => { present = false; },
  };
}

const settings = {league_id: '12922', season: 'just_started', start_date_override: '2026-10-09'};

test('menu uses bound spreadsheet entrypoints', () => {
  const f = fixture();
  f.context.onOpen();
  assert.deepEqual(f.events.filter(e => Array.isArray(e) && e[0] === 'menu'), [
    ['menu', 'Configure and run', 'showScraperSidebar'],
    ['menu', 'Show run status', 'showRunStatus'],
    ['menu', 'Clear pending GitHub submission', 'clearPendingGithubSubmission'],
  ]);
});

test('settings match backend vocabulary and trim input', () => {
  const f = fixture();
  assert.deepEqual(plain(f.context.validateSettings_({...settings, league_id: ' 12922 '})), settings);
  assert.equal(f.context.validateSettings_({...settings, start_date_override: ''}).start_date_override, '');
  assert.equal(f.context.validateSettings_({...settings, start_date_override: '2024-02-29'}).start_date_override, '2024-02-29');
});

test('reject invalid league, season and date before writing', () => {
  const f = fixture();
  for (const bad of [
    {...settings, league_id: ''}, {...settings, league_id: '１２'},
    {...settings, season: '2'}, {...settings, start_date_override: '2026-02-30'},
    {...settings, start_date_override: '2026-1-09'},
    {...settings, start_date_override: '0000-01-01'},
  ]) assert.throws(() => f.context.saveSettingsFromSidebar(bad));
  assert.equal(f.rows().length, 0);
});

test('save preserves metadata and unknown rows and hides config', () => {
  const initial = [
    ['league_id', 'old'], ['season', 'preseason'], ['league_name', 'FNH'],
    ['last_run', 'previous-success'], ['run_status', 'complete'], ['custom', 'keep'],
  ];
  const f = fixture(initial);
  const state = f.context.saveSettingsFromSidebar(settings);
  assert.equal(state.league_id, '12922');
  assert.equal(state.season, 'just_started');
  assert.equal(state.last_run, 'previous-success');
  assert.deepEqual(f.rows().find(row => row[0] === 'custom'), ['custom', 'keep']);
  assert(f.events.includes('hide'));
  assert(f.events.includes('flush'));
  assert.equal(f.events.at(-1), 'release');
});

test('missing config tab can be created without touching stats tabs', () => {
  const f = fixture(); f.missing();
  f.context.saveSettingsFromSidebar(settings);
  assert(f.events.some(e => Array.isArray(e) && e[0] === 'insert' && e[1] === '_config'));
  assert.equal(f.rows().length, 4);
});

test('duplicate config keys are rejected rather than changing only one copy', () => {
  const f = fixture([['league_id', '1'], ['league_id', '2']]);
  assert.throws(() => f.context.saveSettingsFromSidebar(settings), /Duplicate key/);
  assert.deepEqual(f.rows(), [['league_id', '1'], ['league_id', '2']]);
  assert.equal(f.events.at(-1), 'release');
});

test('sidebar data never includes script secrets or unrelated config rows', () => {
  const f = fixture([['BACKEND_SECRET', 'secret-in-sheet'], ['league_id', '12922']]);
  const state = f.context.getSidebarState();
  assert.equal(state.league_id, '12922');
  assert(!JSON.stringify(state).includes('secret'));
});

test('required backend properties are validated before HTTP calls', () => {
  for (const properties of [
    {BACKEND_SECRET: ''}, {BACKEND_URL: ''}, {BACKEND_URL: 'http://example.com'},
    {BACKEND_URL: 'https://example.com/path'}, {BACKEND_URL: 'https://user:pass@example.com'},
  ]) {
    const f = fixture(); Object.assign(f.properties, properties);
    assert.throws(() => f.context.runFromSidebar(settings));
    assert.equal(f.events.filter(e => Array.isArray(e) && e[0] === 'fetch').length, 0);
  }
});

test('request sends active sheet ID only and refuses redirects', () => {
  const f = fixture();
  const result = f.context.runFromSidebar(settings);
  const fetch = f.events.find(e => Array.isArray(e) && e[0] === 'fetch');
  assert.equal(fetch[1], 'https://example.run.app/scrape');
  assert.deepEqual(plain(fetch[2]), {
    method: 'post', contentType: 'application/json',
    headers: {Authorization: 'Bearer private-secret'},
    payload: '{"spreadsheet_id":"sheet-123"}', muteHttpExceptions: true,
    followRedirects: false,
  });
  assert.equal(result.ok, true);
  assert(!JSON.stringify(result).includes('private-secret'));
  assert(f.events.indexOf('flush') < f.events.indexOf(fetch));
  assert.equal(f.events.at(-1), 'release');
});

test('lock contention prevents settings writes and network calls', () => {
  const f = fixture(); f.lock(false);
  assert.throws(() => f.context.runFromSidebar(settings), /already in progress/);
  assert.equal(f.rows().length, 0);
  assert(!f.events.includes('release'));
});

test('running status blocks new runs even after another execution released its lock', () => {
  const f = fixture([['run_status', 'running']]);
  assert.throws(() => f.context.runFromSidebar(settings), /marked as running/);
  assert.equal(f.events.at(-1), 'release');
  assert(!f.events.some(e => Array.isArray(e) && e[0] === 'fetch'));
});

test('HTTP failures display safe messages without exposing response bodies', () => {
  const f = fixture();
  for (const status of [401, 403, 422, 500, 502, 503, 504, 302, 200]) {
    const result = f.context.parseBackendResponse_({
      getResponseCode: () => status,
      getContentText: () => 'private-secret',
    });
    assert.equal(result.ok, false);
    assert(!result.message.includes('private-secret'));
  }
  assert.equal(f.context.parseBackendResponse_({
    getResponseCode: () => 200, getContentText: () => 'null',
  }).ok, false);
});

test('network error is sanitized, not retried, and lock is released', () => {
  const f = fixture(); let count = 0;
  f.context.UrlFetchApp.fetch = () => { count++; throw new Error('private-secret'); };
  assert.throws(() => f.context.runFromSidebar(settings), /Check run status/);
  assert.equal(count, 1);
  assert.equal(f.events.at(-1), 'release');
});

test('optional sharing requires explicit opt-in and a service-account email', () => {
  const f = fixture();
  f.context.runFromSidebar(settings);
  assert(!f.events.some(e => Array.isArray(e) && e[0] === 'share'));
  f.properties.AUTO_SHARE_SERVICE_ACCOUNT = 'true';
  assert.throws(() => f.context.runFromSidebar(settings), /SERVICE_ACCOUNT_EMAIL/);
  f.properties.SERVICE_ACCOUNT_EMAIL = 'scraper@project.iam.gserviceaccount.com';
  f.context.runFromSidebar(settings);
  assert(f.events.some(e => Array.isArray(e) && e[0] === 'share'
    && e[1] === 'scraper@project.iam.gserviceaccount.com'));
});

test('sharing failure is reported safely and releases the lock', () => {
  const f = fixture();
  Object.assign(f.properties, {
    AUTO_SHARE_SERVICE_ACCOUNT: 'true',
    SERVICE_ACCOUNT_EMAIL: 'scraper@project.iam.gserviceaccount.com',
  });
  f.spreadsheet.addEditor = () => { throw new Error('private detail'); };
  assert.throws(() => f.context.runFromSidebar(settings), /Share it manually/);
  assert.equal(f.events.at(-1), 'release');
  assert(!f.events.some(e => Array.isArray(e) && e[0] === 'fetch'));
});

test('sidebar client JavaScript compiles and renders text without HTML injection', () => {
  const html = fs.readFileSync(path.join(__dirname, '../google_apps_script/Sidebar.html'), 'utf8');
  const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  new vm.Script(script);
  assert(!script.includes('.innerHTML'));
  assert(script.includes('.textContent'));
});

function githubFixture(rows = []) {
  const f = fixture(rows);
  delete f.properties.BACKEND_URL;
  delete f.properties.BACKEND_SECRET;
  Object.assign(f.properties, {
    BACKEND_TYPE: 'github_actions',
    GITHUB_REPOSITORY: 'edvard-munch/yahoo_roster_scraper',
    GITHUB_TOKEN: 'github-private-token',
  });
  f.context.UrlFetchApp.fetch = (url, options) => {
    f.events.push(['fetch', url, options]);
    return {getResponseCode: () => 204, getContentText: () => ''};
  };
  return f;
}

test('GitHub mode dispatches the workflow without Cloud Run credentials', () => {
  const f = githubFixture([['run_status', 'complete'], ['last_run', 'old-success']]);
  const result = f.context.runFromSidebar(settings);
  const fetch = f.events.find(e => Array.isArray(e) && e[0] === 'fetch');
  assert.equal(fetch[1], 'https://api.github.com/repos/edvard-munch/yahoo_roster_scraper/actions/workflows/scrape-google-sheet.yml/dispatches');
  assert.deepEqual(plain(fetch[2]), {
    method: 'post', contentType: 'application/json',
    headers: {
      Authorization: 'Bearer github-private-token',
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
    },
    payload: '{"ref":"master","inputs":{"spreadsheet_id":"sheet-123"}}',
    muteHttpExceptions: true, followRedirects: false,
  });
  assert.equal(result.ok, true);
  assert.equal(result.submitted, true);
  assert(result.message.includes('not completed'));
  assert.equal(result.state.run_status, 'complete'); // Last backend run, not the dispatch.
  assert.equal(result.state.last_run, 'old-success');
  assert.equal(result.state.github_dispatch_pending, true);
  assert(!JSON.stringify(result).includes('github-private-token'));
  assert.equal(f.events.at(-1), 'release');
});

test('provider selection fails on unknown provider without using either backend', () => {
  const f = fixture(); f.properties.BACKEND_TYPE = 'other';
  assert.throws(() => f.context.runFromSidebar(settings), /BACKEND_TYPE/);
  assert(!f.events.some(e => Array.isArray(e) && e[0] === 'fetch'));
});

test('GitHub properties reject missing token and unsafe repository/workflow/ref', () => {
  for (const changed of [
    {GITHUB_TOKEN: ''}, {GITHUB_REPOSITORY: ''},
    {GITHUB_REPOSITORY: 'https://evil.test/repo'},
    {GITHUB_REPOSITORY: 'owner/repo/extra'},
    {GITHUB_WORKFLOW: '../other.yml'}, {GITHUB_WORKFLOW: 'a.yml?token=secret'},
    {GITHUB_REF: 'feature-branch'},
  ]) {
    const f = githubFixture(); Object.assign(f.properties, changed);
    assert.throws(() => f.context.runFromSidebar(settings));
    assert(!f.events.some(e => Array.isArray(e) && e[0] === 'fetch'));
  }
});

test('explicit Cloud Run mode does not require or use GitHub properties', () => {
  const f = fixture(); f.properties.BACKEND_TYPE = 'cloud_run';
  f.properties.GITHUB_TOKEN = 'unused-token';
  f.properties.GITHUB_REPOSITORY = 'invalid repository';
  assert.equal(f.context.runFromSidebar(settings).ok, true);
  const request = f.events.find(e => Array.isArray(e) && e[0] === 'fetch');
  assert.equal(request[1], 'https://example.run.app/scrape');
  assert(!JSON.stringify(request).includes('unused-token'));
});

test('pending dispatch blocks duplicate dispatch and settings edits', () => {
  const f = githubFixture(); f.context.runFromSidebar(settings);
  assert.throws(() => f.context.runFromSidebar(settings), /submission is pending/);
  assert.throws(() => f.context.saveSettingsFromSidebar({...settings, league_id: 'other'}));
  assert.throws(() => f.context.saveSettingsFromSidebar({...settings, league_id: '999'}), /submission is pending/);
  assert.equal(f.events.filter(e => Array.isArray(e) && e[0] === 'fetch').length, 1);
});

test('pending marker clears when Python starts and normal running guard remains', () => {
  const f = githubFixture([['run_started_at', 'old-start'], ['run_status', 'complete']]);
  f.context.runFromSidebar(settings);
  f.rows()[0][1] = 'new-start';
  f.rows()[1][1] = 'running';
  assert.equal(f.context.getSidebarState().github_dispatch_pending, false);
  assert.equal(f.properties.GITHUB_DISPATCH_PENDING, undefined);
  assert.throws(() => f.context.runFromSidebar(settings), /marked as running/);
});

test('GitHub 4xx response reports safe failure and clears pending marker', () => {
  for (const code of [401, 403, 404, 422, 429]) {
    const f = githubFixture(); let count = 0;
    f.context.UrlFetchApp.fetch = () => {
      count++;
      return {getResponseCode: () => code, getContentText: () => 'github-private-token'};
    };
    const result = f.context.runFromSidebar(settings);
    assert.equal(result.ok, false);
    assert.equal(result.state.github_dispatch_pending, false);
    assert(!JSON.stringify(result).includes('github-private-token'));
    assert.equal(count, 1); // No automatic fallback or retry.
    assert.equal(f.events.at(-1), 'release');
  }
});

test('ambiguous GitHub network/5xx failures retain pending guard without fallback', () => {
  const f = githubFixture(); let count = 0;
  f.context.UrlFetchApp.fetch = () => { count++; throw new Error('github-private-token'); };
  assert.throws(() => f.context.runFromSidebar(settings), /outcome is unknown/);
  assert.equal(count, 1);
  assert.equal(f.context.getSidebarState().github_dispatch_pending, true);
  assert.equal(f.events.at(-1), 'release');
  const g = githubFixture();
  g.context.UrlFetchApp.fetch = () => ({getResponseCode: () => 502});
  assert.equal(g.context.runFromSidebar(settings).state.github_dispatch_pending, true);
});

test('clearing pending marker requires confirmation and does not cancel jobs', () => {
  const f = githubFixture(); f.context.runFromSidebar(settings);
  f.context.SpreadsheetApp.getUi().alert = () => 'NO';
  f.context.clearPendingGithubSubmission();
  assert.equal(f.context.getSidebarState().github_dispatch_pending, true);
  f.context.SpreadsheetApp.getUi().alert = () => 'YES';
  f.context.clearPendingGithubSubmission();
  assert.equal(f.context.getSidebarState().github_dispatch_pending, false);
  assert.equal(f.events.filter(e => Array.isArray(e) && e[0] === 'fetch').length, 1);
});

test('pending marker cannot be cleared while Python is running', () => {
  const f = githubFixture([['run_status', 'running']]);
  f.properties.GITHUB_DISPATCH_PENDING = '{}';
  f.context.SpreadsheetApp.getUi().alert = () => 'YES';
  assert.throws(() => f.context.clearPendingGithubSubmission(), /marked as running/);
});

test('saving seeds timezone from spreadsheet settings when missing or blank', () => {
  for (const rows of [[], [['timezone', '']]]) {
    const f = fixture(rows);
    f.context.saveSettingsFromSidebar(settings);
    assert.equal(f.context.getSidebarState().timezone, 'Europe/Moscow');
    assert.equal(f.rows().filter(row => row[0] === 'timezone').length, 1);
  }
});

test('saving preserves an explicitly configured timezone', () => {
  const f = fixture([['timezone', 'America/New_York']]);
  f.context.saveSettingsFromSidebar(settings);
  assert.equal(f.context.getSidebarState().timezone, 'America/New_York');
});
