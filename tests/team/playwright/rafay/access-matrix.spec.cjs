// Two-role access matrix for the checkout and check-in workflows      (owner: Rafay Imran)
//
// Each test is one access decision: a role performs one ordinary application action through the
// browser (page load or the same form POST the UI sends, with that role's own session and CSRF
// token). The test asserts the expected decision, the visible outcome and, for writes, the persisted
// asset state. Every observed row is also written to output/playwright/security/access-matrix.json
// (role, action, expected, observed, evidence) for the security report.
const fs = require('node:fs');
const path = require('node:path');
const s = require('../support/fixtures.cjs');
const { test, expect, data } = s;

const rows = [];
function record(row) { rows.push({ ...row, test: test.info().title }); }
test.afterAll(() => {
  const dir = path.join(s.OUTPUT, 'security');
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, 'access-matrix.json');
  const previous = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : [];
  const ids = new Set(rows.map((r) => r.id));
  fs.writeFileSync(file, JSON.stringify([...previous.filter((r) => !ids.has(r.id)), ...rows]
    .sort((a, b) => a.id.localeCompare(b.id)), null, 2));
});

/** POST a browser form exactly as the UI does, with the page's own session cookie and CSRF token. */
async function postForm(page, url, fields) {
  const token = await page.locator('meta[name="csrf-token"]').getAttribute('content');
  return page.request.post(url, { form: { _token: token, ...fields }, maxRedirects: 0 });
}

const loanFields = () => ({ checkout_to_type: 'user', assigned_user: String(data.students[0].id),
  status_id: String(data.status.ready.id), expected_checkin: '2090-04-15' });

test.describe('Access matrix: lab technician (assets.view, assets.checkout, assets.checkin)', () => {
  test('AC-01 technician opens the checkout form: allowed', async ({ technician: page, request }) => {
    const id = data.assets['RAF-AC-01'];
    await s.resetAsset(request, id);
    const response = await page.goto(`/hardware/${id}/checkout`);
    expect(response.status()).toBe(200);
    await expect(page.locator('#checkout_form')).toBeVisible();
    record({ id: 'AC-01', role: 'technician', action: `GET /hardware/${id}/checkout`, expected: 'allowed: 200 and form shown',
      observed: `HTTP ${response.status()}, #checkout_form visible`, evidence: 'screenshot + trace in Playwright report' });
  });

  test('AC-02 technician submits a checkout: allowed and saved', async ({ technician: page, request }) => {
    const id = data.assets['RAF-AC-02'];
    const before = await s.resetAsset(request, id);
    await page.goto(`/hardware/${id}/checkout`);
    const response = await postForm(page, `/hardware/${id}/checkout`, loanFields());
    expect(response.status()).toBe(302);
    const saved = await s.readAsset(request, id);
    expect(saved.assigned_to.id).toBe(data.students[0].id);
    expect(saved.checkout_counter).toBe(before.checkout_counter + 1);
    record({ id: 'AC-02', role: 'technician', action: `POST /hardware/${id}/checkout`, expected: 'allowed: loan saved',
      observed: `HTTP 302 to ${response.headers().location}; assigned_to=${saved.assigned_to.username}, checkout_counter ${before.checkout_counter}->${saved.checkout_counter}`,
      evidence: 'REST read-back GET /api/v1/hardware/{id}' });
  });

  test('AC-03 technician submits a check-in: allowed and saved', async ({ technician: page, request }) => {
    const id = data.assets['RAF-AC-03'];
    const before = await s.loanAsset(request, id);
    await page.goto(`/hardware/${id}/checkin`);
    const response = await postForm(page, `/hardware/${id}/checkin`, { status_id: String(data.status.repair.id) });
    expect(response.status()).toBe(302);
    const saved = await s.readAsset(request, id);
    expect(saved.assigned_to).toBeNull();
    expect(saved.checkin_counter).toBe(before.checkin_counter + 1);
    record({ id: 'AC-03', role: 'technician', action: `POST /hardware/${id}/checkin`, expected: 'allowed: return saved',
      observed: `HTTP 302; assigned_to=null, status=${saved.status_label.name}, checkin_counter ${before.checkin_counter}->${saved.checkin_counter}`,
      evidence: 'REST read-back GET /api/v1/hardware/{id}' });
  });

  test('AC-04 technician opens the asset edit form: denied (no assets.edit)', async ({ technician: page }) => {
    const id = data.assets['RAF-AC-01'];
    const response = await page.goto(`/hardware/${id}/edit`);
    expect(response.status()).toBe(403);
    record({ id: 'AC-04', role: 'technician', action: `GET /hardware/${id}/edit`, expected: 'denied: 403 (outside the role)',
      observed: `HTTP ${response.status()}`, evidence: 'Playwright response status' });
  });
});

test.describe('Access matrix: read-only reviewer (assets.view)', () => {
  test('AC-05 reviewer views the laptop record: allowed, with no checkout or check-in action', async ({ reviewer: page, request }) => {
    const id = data.assets['RAF-AC-04'];
    await s.loanAsset(request, id);
    const response = await page.goto(`/hardware/${id}`);
    expect(response.status()).toBe(200);
    await expect(page.locator('body')).toContainText('RAF-AC-04');
    await expect(page.locator(`a[href$="/hardware/${id}/checkout"], a[href$="/hardware/${id}/checkin"]`)).toHaveCount(0);
    record({ id: 'AC-05', role: 'reviewer', action: `GET /hardware/${id}`, expected: 'allowed: record visible, no loan actions offered',
      observed: `HTTP ${response.status()}, no checkout/checkin links`, evidence: 'screenshot in Playwright report' });
  });

  test('AC-06 reviewer opens the checkout form: denied', async ({ reviewer: page, request }) => {
    const id = data.assets['RAF-AC-05'];
    await s.resetAsset(request, id);
    const response = await page.goto(`/hardware/${id}/checkout`);
    expect(response.status()).toBe(403);
    await expect(page.locator('#checkout_form')).toHaveCount(0);
    record({ id: 'AC-06', role: 'reviewer', action: `GET /hardware/${id}/checkout`, expected: 'denied: 403, no form',
      observed: `HTTP ${response.status()}, no form`, evidence: 'screenshot in Playwright report' });
  });

  test('AC-07 reviewer submits a checkout: denied and nothing saved', async ({ reviewer: page, request }) => {
    const id = data.assets['RAF-AC-05'];
    const before = await s.resetAsset(request, id);
    await page.goto(`/hardware/${id}`);
    const response = await postForm(page, `/hardware/${id}/checkout`, loanFields());
    expect(response.status()).toBe(403);
    const after = await s.readAsset(request, id);
    expect(after.assigned_to).toBeNull();
    expect(after.checkout_counter).toBe(before.checkout_counter);
    record({ id: 'AC-07', role: 'reviewer', action: `POST /hardware/${id}/checkout`, expected: 'denied: 403, asset unchanged',
      observed: `HTTP ${response.status()}; assigned_to=null, checkout_counter ${before.checkout_counter}->${after.checkout_counter}`,
      evidence: 'REST read-back GET /api/v1/hardware/{id}' });
  });

  test('AC-08 reviewer opens the check-in form: denied', async ({ reviewer: page, request }) => {
    const id = data.assets['RAF-AC-06'];
    await s.loanAsset(request, id);
    const response = await page.goto(`/hardware/${id}/checkin`);
    expect(response.status()).toBe(403);
    record({ id: 'AC-08', role: 'reviewer', action: `GET /hardware/${id}/checkin`, expected: 'denied: 403',
      observed: `HTTP ${response.status()}`, evidence: 'screenshot in Playwright report' });
  });

  test('AC-09 reviewer submits a check-in: denied and the loan is kept', async ({ reviewer: page, request }) => {
    const id = data.assets['RAF-AC-06'];
    const before = await s.loanAsset(request, id);
    await page.goto(`/hardware/${id}`);
    const response = await postForm(page, `/hardware/${id}/checkin`, { status_id: String(data.status.ready.id) });
    expect(response.status()).toBe(403);
    const after = await s.readAsset(request, id);
    expect(after.assigned_to.id).toBe(data.students[0].id);
    expect(after.checkin_counter).toBe(before.checkin_counter);
    record({ id: 'AC-09', role: 'reviewer', action: `POST /hardware/${id}/checkin`, expected: 'denied: 403, loan kept',
      observed: `HTTP ${response.status()}; assigned_to=${after.assigned_to.username}, checkin_counter ${before.checkin_counter}->${after.checkin_counter}`,
      evidence: 'REST read-back GET /api/v1/hardware/{id}' });
  });
});

test.describe('Control: CSRF protection on the checkout form', () => {
  test('AC-11 a technician checkout POST without the form token is refused and nothing is saved', async ({ technician: page, request }) => {
    const id = data.assets['RAF-AC-02'];
    const before = await s.resetAsset(request, id);
    await page.goto(`/hardware/${id}/checkout`);
    await page.waitForLoadState('networkidle');
    // Leave the form before posting: its background requests (pickers, Livewire panel) would otherwise
    // be the "next request" after the POST and consume the one-shot flash message.
    await page.goto('about:blank');
    // Same session cookie and fields as AC-02, but no _token: what a cross-site form post would send.
    const response = await page.request.post(`/hardware/${id}/checkout`, { form: loanFields(), maxRedirects: 0 });
    // Snipe-IT turns Laravel's 419 into a same-origin redirect with a flash message (app/Exceptions/Handler.php).
    expect(response.status()).toBe(302);
    const location = response.headers().location;
    expect(new URL(location).origin).toBe(new URL(data.baseUrl).origin); // same-origin redirect only
    await page.goto(location);
    await expect(s.flash(page).filter({ hasText: 'Your form session has expired. Please try again.' })).toBeVisible();
    const after = await s.readAsset(request, id);
    expect(after.assigned_to).toBeNull();
    expect(after.checkout_counter).toBe(before.checkout_counter);
    record({ id: 'AC-11', role: 'technician', action: `POST /hardware/${id}/checkout without _token`, expected: 'denied: CSRF check fails, asset unchanged',
      observed: `HTTP ${response.status()} to same-origin ${new URL(location).pathname} with "Your form session has expired"; assigned_to=null, checkout_counter ${before.checkout_counter}->${after.checkout_counter}`,
      evidence: 'REST read-back GET /api/v1/hardware/{id}' });
  });
});

test.describe('Access matrix: no session', () => {
  test('AC-10 a visitor with no session is sent to sign in', async ({ page, request }) => {
    const id = data.assets['RAF-AC-01'];
    await s.resetAsset(request, id);
    await page.goto(`/hardware/${id}/checkout`);
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('button', { name: /^login$/i })).toBeVisible();
    record({ id: 'AC-10', role: 'anonymous', action: `GET /hardware/${id}/checkout`, expected: 'denied: redirect to /login',
      observed: `landed on ${new URL(page.url()).pathname}`, evidence: 'screenshot in Playwright report' });
  });
});
