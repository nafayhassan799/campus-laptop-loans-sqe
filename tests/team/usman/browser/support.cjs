// Fixtures and helpers for Muhammad Usman's browser use cases.
// Shared sign-in/API helpers from the team's Playwright setup (Rafay) were not on any branch when this
// was written; these are small, local equivalents with the same shape so they can be swapped out.
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { expect } = require('@playwright/test');

const dataFile = process.env.SQE_BROWSER_DATA_FILE
  || path.resolve(__dirname, '../../../../output/usman/fixtures.json');
const data = JSON.parse(fs.readFileSync(dataFile, 'utf8'));

const today = () => new Date().toISOString().slice(0, 10);
const addDays = (days) => new Date(Date.now() + days * 86400000).toISOString().slice(0, 10);

async function call(request, who, method, url, body) {
  const response = await request.fetch(`/api/v1/${url}`, {
    method,
    headers: { Authorization: `Bearer ${data[who].token}`, Accept: 'application/json', 'Content-Type': 'application/json' },
    data: body === undefined ? undefined : JSON.stringify(body),
  });
  expect(response.status(), `${method} ${url}`).toBeLessThan(500);
  return response.json();
}

/** Create (once) or fetch a dedicated laptop so each browser case owns its own record. */
async function ensureAsset(request, tag) {
  const found = await call(request, 'admin', 'GET', `hardware/bytag/${encodeURIComponent(tag)}`);
  if (found?.id) { return found.id; }
  const created = await call(request, 'admin', 'POST', 'hardware',
    { asset_tag: tag, model_id: data.model.id, status_id: data.ready.id });
  expect(created.status, JSON.stringify(created)).toBe('success');
  return created.payload.id;
}

/** Deployable, unassigned, unnamed, default location: a known starting point. */
async function resetAsset(request, id) {
  await call(request, 'technician', 'POST', `hardware/${id}/checkin`,
    { status_id: data.ready.id, clear_name: '1', location_id: null });
  const asset = await call(request, 'technician', 'GET', `hardware/${id}`);
  expect(asset.assigned_to).toBeNull();
  return asset;
}

async function loan(request, id, studentIndex = 0, due = null) {
  const body = { checkout_to_type: 'user', assigned_user: data.students[studentIndex].id };
  if (due) { body.expected_checkin = due; }
  const result = await call(request, 'technician', 'POST', `hardware/${id}/checkout`, body);
  expect(result.status, JSON.stringify(result)).toBe('success');
}

const readAsset = (request, id) => call(request, 'technician', 'GET', `hardware/${id}`);

async function history(request, id) {
  const events = [];
  for (let offset = 0; ; offset += 200) {
    const report = await call(request, 'admin', 'GET',
      `reports/activity?item_type=asset&item_id=${id}&limit=200&offset=${offset}&sort=id&order=asc`);
    events.push(...report.rows.map((row) => ({
      id: row.id, action: row.action_type, target: row.target?.id ?? null,
      date: row.action_date?.datetime ?? null,
    })));
    if (!report.rows.length || events.length >= report.total) { return events; }
  }
}
const count = (events, action) => events.filter((e) => e.action === action).length;

async function signIn(page, account = data.technician) {
  await page.goto('/login');
  await page.locator('[name="username"]').fill(account.username);
  await page.locator('[name="password"]').fill(account.password);
  await page.getByRole('button', { name: /log in|sign in|login/i }).click();
  await expect(page).not.toHaveURL(/\/login(?:[/?#]|$)/);
  // Let the dashboard's own background requests finish: a late request can consume a one-shot flash message.
  await page.waitForLoadState('networkidle');
}

/** Pick an option in a select2 control (plain or ajax-backed). */
async function choose(page, field, optionText, search) {
  const select = page.locator(`select[name="${field}"]`);
  await expect(select).toHaveCount(1);
  await select.locator('+ .select2').getByRole('combobox').click();
  if (search) {
    await page.locator('.select2-container--open .select2-search__field').fill(search);
  }
  await page.locator('.select2-container--open').getByRole('option', { name: optionText }).first().click();
}

async function submit(page, action) {
  // Background requests (select2 look-ups) that finish after the redirect can swallow the one-shot flash message.
  await page.waitForLoadState('networkidle');
  return page.locator(`form[action*="/${action}"]`).locator('[type="submit"]').last().click();
}

/** The check-in notes setting is global, so it is switched on only inside the test and always restored. */
function setNotesRequired(on) {
  const dbCommand = (process.env.SQE_DB_CMD || '').split(' ').filter(Boolean);
  const artisan = (process.env.SQE_ARTISAN || '').split(' ').filter(Boolean);
  if (!dbCommand.length || !artisan.length) {
    throw new Error('Set SQE_DB_CMD and SQE_ARTISAN so the notes setting can be toggled and the cache cleared');
  }
  const sql = spawnSync(dbCommand[0], [...dbCommand.slice(1), '-e', `update settings set require_checkinout_notes=${on ? 1 : 0}`], { encoding: 'utf8' });
  if (sql.status !== 0) { throw new Error(`settings update failed: ${sql.stderr}`); }
  const cache = spawnSync(artisan[0], [...artisan.slice(1), 'cache:clear'], { encoding: 'utf8', cwd: path.resolve(__dirname, '../../../..') });
  if (cache.status !== 0) { throw new Error(`cache:clear failed: ${cache.stderr}`); }
}

module.exports = { data, today, addDays, call, ensureAsset, resetAsset, loan, readAsset, history, count,
  signIn, choose, submit, setNotesRequired };
