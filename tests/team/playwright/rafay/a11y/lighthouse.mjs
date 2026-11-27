// Authenticated Lighthouse runs (accessibility, best practices, SEO)   (owner: Rafay Imran)
//
//   SQE_A11Y_LABEL=before node rafay/a11y/lighthouse.mjs
//
// Signs in as the lab technician in a Chromium profile with remote debugging, resets the two
// screen laptops through the API (one available, one on loan), and runs Lighthouse against the
// login, checkout and checkin screens in that same signed-in browser. Lighthouse's storage reset
// is disabled so the session survives. Desktop form factor and no throttling, so before and after
// runs are comparable on the same machine. Raw .json and .html reports go to
// output/playwright/a11y/<label>/lighthouse-<screen>.{json,html}.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import lighthouse from 'lighthouse';

const require = createRequire(import.meta.url);
const { chromium, request: apiRequest } = require('@playwright/test');
// fileURLToPath, not URL.pathname: on Windows pathname is "/C:/..." and path.resolve breaks.
const here = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(here, '../../../../../output/playwright');
const data = JSON.parse(fs.readFileSync(process.env.SQE_FIXTURES_FILE || path.join(output, 'fixtures.json'), 'utf8'));
const { assertLocalTarget } = require('../../support/local-target.cjs');
// Checked before the admin token or the technician password is used below.
const baseURL = assertLocalTarget(process.env.SQE_BASE_URL || data.baseUrl, data.baseUrl);
const label = process.env.SQE_A11Y_LABEL || 'latest';
const outDir = path.join(output, 'a11y', label);
const PORT = 9333;

const api = await apiRequest.newContext({
  baseURL, extraHTTPHeaders: { Authorization: `Bearer ${data.admin.token}`, Accept: 'application/json' },
});
async function call(method, url, body) {
  const response = await api.fetch(`/api/v1/${url}`, { method, data: body });
  const json = await response.json();
  if (json.status === 'error') { throw new Error(`${method} ${url}: ${JSON.stringify(json.messages)}`); }
  return json;
}
async function reset(id) {
  const asset = await call('GET', `hardware/${id}`);
  if (asset.assigned_to) { await call('POST', `hardware/${id}/checkin`, { status_id: data.status.ready.id }); }
  await call('PATCH', `hardware/${id}`, { status_id: data.status.ready.id, name: null, expected_checkin: null });
}
const checkoutId = data.assets['RAF-A11Y-CO'];
const checkinId = data.assets['RAF-A11Y-CI'];
await reset(checkoutId);
await reset(checkinId);
await call('POST', `hardware/${checkinId}/checkout`, { checkout_to_type: 'user', assigned_user: data.students[0].id, expected_checkin: '2090-04-15' });

const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'sqe-lighthouse-'));
const context = await chromium.launchPersistentContext(profile, {
  headless: true,
  executablePath: process.env.SQE_CHROME_PATH || undefined,
  args: [`--remote-debugging-port=${PORT}`],
  viewport: { width: 1350, height: 940 },
});
const flags = {
  port: PORT, output: ['json', 'html'], logLevel: 'error', disableStorageReset: true,
  onlyCategories: ['accessibility', 'best-practices', 'seo'],
  formFactor: 'desktop', screenEmulation: { mobile: false, width: 1350, height: 940, deviceScaleFactor: 1, disabled: false },
  throttlingMethod: 'provided',
};

async function audit(screen, url) {
  const result = await lighthouse(`${baseURL}${url}`, flags);
  fs.mkdirSync(outDir, { recursive: true });
  const [json, html] = result.report;
  fs.writeFileSync(path.join(outDir, `lighthouse-${screen}.json`), json);
  fs.writeFileSync(path.join(outDir, `lighthouse-${screen}.html`), html);
  const lhr = result.lhr;
  if (lhr.finalDisplayedUrl.includes('/login') && screen !== 'login') {
    throw new Error(`${screen}: Lighthouse was redirected to the login page; the session was lost`);
  }
  const scores = Object.fromEntries(Object.entries(lhr.categories).map(([key, cat]) => [key, Math.round(cat.score * 100)]));
  const failed = Object.values(lhr.audits)
    .filter((a) => a.score !== null && a.score < 1 && ['binary', 'numeric'].includes(a.scoreDisplayMode))
    .map((a) => ({ id: a.id, title: a.title, items: a.details?.items?.length ?? 0 }));
  return { screen, url: lhr.finalDisplayedUrl, lighthouseVersion: lhr.lighthouseVersion, scores, failed };
}

const results = [];
try {
  // Unauthenticated first, then sign in inside the same profile Lighthouse uses.
  results.push(await audit('login', '/login'));
  const page = context.pages()[0] || await context.newPage();
  await page.goto(`${baseURL}/login`);
  await page.locator('input[name="username"]').fill(data.technician.username);
  await page.locator('input[name="password"]').fill(data.technician.password);
  await page.getByRole('button', { name: /^login$/i }).click();
  await page.waitForURL((u) => !u.pathname.startsWith('/login'));
  results.push(await audit('checkout', `/hardware/${checkoutId}/checkout`));
  results.push(await audit('checkin', `/hardware/${checkinId}/checkin`));
} finally {
  await context.close();
  await api.dispose();
  fs.rmSync(profile, { recursive: true, force: true });
}
fs.writeFileSync(path.join(outDir, 'lighthouse-summary.json'), JSON.stringify(results, null, 2));
for (const r of results) {
  console.log(`${r.screen.padEnd(9)} a11y ${r.scores.accessibility}  best-practices ${r.scores['best-practices']}  seo ${r.scores.seo}`);
  for (const f of r.failed) { console.log(`   - ${f.id} (${f.items}) ${f.title}`); }
}
