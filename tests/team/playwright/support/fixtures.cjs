// Shared helpers for the team Playwright suite (owner: Rafay Imran).
//
// Everything a spec needs to sign in, drive the select2 pickers, reset its own laptop
// to a known state and read the saved result back. Credentials, API tokens and stored
// sessions come from output/playwright/ (git-ignored), written by seed.py and auth.setup.cjs.
const fs = require('node:fs');
const path = require('node:path');
const { test: base, expect } = require('@playwright/test');

const OUTPUT = path.resolve(__dirname, '../../../../output/playwright');
const fixtureFile = process.env.SQE_FIXTURES_FILE || path.join(OUTPUT, 'fixtures.json');
if (!fs.existsSync(fixtureFile)) {
  throw new Error(`Missing ${fixtureFile}. Run: python3 -B tests/team/playwright/seed.py --admin-id <id>`);
}
const data = JSON.parse(fs.readFileSync(fixtureFile, 'utf8'));
const sessionFile = (role) => path.join(OUTPUT, '.auth', `${role}.json`);

// ---------------------------------------------------------------- REST read-back

/** Call the REST API as 'admin' or 'technician'; returns parsed JSON. */
async function call(request, who, method, url, body) {
  const response = await request.fetch(`/api/v1/${url}`, {
    method,
    headers: { Authorization: `Bearer ${data[who].token}`, Accept: 'application/json', 'Content-Type': 'application/json' },
    data: body === undefined ? undefined : JSON.stringify(body),
  });
  expect(response.status(), `${method} ${url}`).toBeLessThan(500);
  return response.json();
}

const readAsset = (request, id) => call(request, 'admin', 'GET', `hardware/${id}`);

/** Every activity-log row for one asset, oldest first: [{action, note, target}] */
async function history(request, id) {
  const report = await call(request, 'admin', 'GET',
    `reports/activity?item_type=asset&item_id=${id}&limit=500&sort=id&order=asc`);
  return report.rows.map((row) => ({
    id: row.id, action: row.action_type, note: row.note, target: row.target && row.target.id,
  }));
}
const countActions = (events, action) => events.filter((event) => event.action === action).length;

/** Known starting point: unassigned, no due date, no name, deployable "SQE Ready to Deploy". */
async function resetAsset(request, id) {
  let asset = await readAsset(request, id);
  if (asset.assigned_to) {
    const result = await call(request, 'admin', 'POST', `hardware/${id}/checkin`,
      { status_id: data.status.ready.id, clear_name: '1' });
    expect(result.status, JSON.stringify(result)).toBe('success');
  }
  const patched = await call(request, 'admin', 'PATCH', `hardware/${id}`,
    { status_id: data.status.ready.id, name: null, notes: null, expected_checkin: null });
  expect(patched.status, JSON.stringify(patched)).toBe('success');
  asset = await readAsset(request, id);
  expect(asset.assigned_to).toBeNull();
  expect(asset.status_label.id).toBe(data.status.ready.id);
  return asset;
}

/** Reset, then lend the laptop to a student through the API (the precondition for a return). */
async function loanAsset(request, id, studentIndex = 0, due = '2090-04-15') {
  await resetAsset(request, id);
  const result = await call(request, 'admin', 'POST', `hardware/${id}/checkout`,
    { checkout_to_type: 'user', assigned_user: data.students[studentIndex].id, expected_checkin: due });
  expect(result.status, JSON.stringify(result)).toBe('success');
  return readAsset(request, id);
}

// ---------------------------------------------------------------- browser helpers

async function signIn(page, account) {
  await page.goto('/login');
  await page.getByLabel(/username/i).fill(account.username);
  // The visible "Password" label is not tied to the input (label for="password" vs id="password-field"),
  // see a11y finding A11Y-01, so the field is located by name until that is fixed everywhere.
  // Set through evaluate so the password never appears in a "Fill" step title in the committed report.
  await page.locator('input[name="password"]').evaluate((input, value) => { input.value = value; }, account.password);
  await page.getByRole('button', { name: /^login$/i }).click();
  await expect(page).not.toHaveURL(/\/login(?:[/?#]|$)/);
  await page.waitForLoadState('networkidle');
}

/** The select2 combobox that stands in for a hidden <select name=...>. */
const picker = (page, field) => page.locator(`select[name="${field}"] + .select2 [role="combobox"]`);

/** Pick an option in a select2 control with the mouse (plain or ajax-backed). */
async function choose(page, field, optionText, search) {
  await picker(page, field).click();
  if (search) {
    await page.locator('.select2-container--open .select2-search__field').fill(search);
  }
  await page.locator('.select2-container--open').getByRole('option', { name: optionText }).first().click();
}

/** Describe the focused element in a stable way for focus-order assertions. */
const focused = (page) => page.evaluate(() => {
  const el = document.activeElement;
  if (el.matches('.select2-selection')) {
    const select = el.closest('.select2').previousElementSibling;
    return `select2:${select && select.getAttribute('name')}`;
  }
  if (el.tagName === 'A') { return `link:${el.innerText.trim()}`; }
  return el.id ? `#${el.id}` : `${el.tagName.toLowerCase()}[name=${el.getAttribute('name')}]`;
});

/** Press Tab until `target` (as reported by focused()) has focus; returns the path walked. */
async function tabTo(page, target, maxPresses = 40) {
  const walked = [];
  for (let i = 0; i < maxPresses; i++) {
    await page.keyboard.press('Tab');
    const now = await focused(page);
    walked.push(now);
    if (now === target) { return walked; }
  }
  throw new Error(`Focus never reached ${target}. Walked: ${walked.join(' > ')}`);
}

/** Choose a select2 option with the keyboard only: open, type to search, Enter. */
async function keyboardChoose(page, search, expectedOption) {
  await page.keyboard.press('Enter');
  const open = page.locator('.select2-container--open');
  await expect(open.locator('.select2-search__field')).toBeFocused();
  await page.keyboard.type(search);
  await expect(open.getByRole('option', { name: expectedOption })).toBeVisible();
  await expect(open.locator('.select2-results__option--highlighted')).toHaveText(expectedOption);
  await page.keyboard.press('Enter');
  await expect(open).toHaveCount(0);
}

const flash = (page) => page.locator('.alert');

// ---------------------------------------------------------------- test fixture

/** `technician` / `reviewer` pages start already signed in from the stored sessions. */
const test = base.extend({
  technician: async ({ browser }, use) => {
    const context = await browser.newContext({ storageState: sessionFile('technician') });
    const page = await context.newPage();
    await use(page);
    await context.close();
  },
  reviewer: async ({ browser }, use) => {
    const context = await browser.newContext({ storageState: sessionFile('reviewer') });
    const page = await context.newPage();
    await use(page);
    await context.close();
  },
});

module.exports = {
  test, expect, data, sessionFile, OUTPUT,
  call, readAsset, history, countActions, resetAsset, loanAsset,
  signIn, picker, choose, focused, tabTo, keyboardChoose, flash,
};
