// Signs each test role in once and stores the session under output/playwright/.auth (git-ignored).
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('@playwright/test');
const { data, signIn, sessionFile } = require('./support/fixtures.cjs');

for (const role of ['technician', 'reviewer']) {
  test(`sign in as ${role}`, async ({ page }) => {
    await signIn(page, data[role]);
    fs.mkdirSync(path.dirname(sessionFile(role)), { recursive: true });
    await page.context().storageState({ path: sessionFile(role) });
    fs.chmodSync(sessionFile(role), 0o600);
  });
}
