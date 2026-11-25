// Full axe-core scan of the screens used by the two loan workflows   (owner: Rafay Imran)
//
//   SQE_A11Y_LABEL=before npx playwright test --project=a11y
//
// Writes the raw axe results for each screen to output/playwright/a11y/<label>/axe-<screen>.json
// and a one-line-per-rule summary to axe-summary.json. The run uses the same seeded laptops,
// viewport and browser every time so the before and after scans are comparable.
const fs = require('node:fs');
const path = require('node:path');
const AxeBuilder = require('@axe-core/playwright').default;
const s = require('../../support/fixtures.cjs');
const { test, expect, data } = s;

const label = process.env.SQE_A11Y_LABEL || 'latest';
const outDir = path.join(s.OUTPUT, 'a11y', label);
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'];

async function scan(page, screen) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, `axe-${screen}.json`), JSON.stringify(results, null, 2));
  const summary = results.violations.map((v) => ({
    screen, rule: v.id, impact: v.impact, nodes: v.nodes.length,
    targets: v.nodes.map((n) => n.target.join(' ')).slice(0, 10), help: v.help,
  }));
  const summaryFile = path.join(outDir, 'axe-summary.json');
  const all = fs.existsSync(summaryFile) ? JSON.parse(fs.readFileSync(summaryFile, 'utf8')).filter((r) => r.screen !== screen) : [];
  fs.writeFileSync(summaryFile, JSON.stringify([...all, ...summary], null, 2));
  test.info().annotations.push({ type: 'axe', description: `${screen}: ${summary.map((r) => `${r.rule}(${r.nodes})`).join(', ') || 'no violations'}` });
  return results;
}

test.describe('axe-core full-page scans', () => {
  test.use({ viewport: { width: 1350, height: 940 } });

  test('login screen', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('button', { name: /^login$/i })).toBeVisible();
    const results = await scan(page, 'login');
    expect(results.passes.length).toBeGreaterThan(0);
  });

  test('checkout screen (UC-R1 key screen)', async ({ technician: page, request }) => {
    const id = data.assets['RAF-A11Y-CO'];
    await s.resetAsset(request, id);
    await page.goto(`/hardware/${id}/checkout`);
    await expect(page.getByRole('button', { name: 'Checkout' })).toBeVisible();
    await page.waitForLoadState('networkidle');
    const results = await scan(page, 'checkout');
    expect(results.passes.length).toBeGreaterThan(0);
  });

  test('checkin screen (UC-R2 key screen)', async ({ technician: page, request }) => {
    const id = data.assets['RAF-A11Y-CI'];
    await s.loanAsset(request, id);
    await page.goto(`/hardware/${id}/checkin`);
    await expect(page.getByRole('button', { name: /checkin/i })).toBeVisible();
    await page.waitForLoadState('networkidle');
    const results = await scan(page, 'checkin');
    expect(results.passes.length).toBeGreaterThan(0);
  });
});
