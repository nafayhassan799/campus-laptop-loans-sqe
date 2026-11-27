const { test, expect } = require('@playwright/test');

const fixtures = JSON.parse(process.env.SQE_BROWSER_DATA ?? '{}');

async function signIn(page, account = fixtures.technician) {
  await page.goto('/login');
  await page.locator('[name="username"]').fill(account.username);
  await page.locator('[name="password"]').fill(account.password);
  await page.getByRole('button', { name: /log in|sign in|login/i }).click();
  await expect(page).not.toHaveURL(/\/login(?:[/?#]|$)/);
}

async function api(request, method, path, options = {}) {
  const response = await request[method](`/api/v1/hardware/${path}`, {
    ...options,
    headers: { Authorization: `Bearer ${fixtures.token}`, Accept: 'application/json' },
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function choose(page, field, text, search) {
  const select = page.locator(`select[name="${field}"]`);
  await expect(select).toHaveCount(1);
  await select.locator('+ .select2').getByRole('combobox').click();
  if (search) {
    await page.locator('.select2-container--open .select2-search__field').fill(search);
  }
  await page.getByRole('option', { name: text, exact: true }).click();
}

function submitForm(page, action) {
  return page.locator(`form[action*="/${action}"]`).locator('[type="submit"]').last().click();
}

for (const [scenario, studentIndex, changedStatus] of [
  ['checkout-main', 0, false], ['checkout-borrower', 1, false], ['checkout-status', 0, true],
]) {
  test(`UC checkout from Hardware Assets: ${scenario}`, async ({ page, request }) => {
    const id = fixtures.cases[scenario];
    const student = fixtures.students[studentIndex];
    await signIn(page);
    await page.goto(`/hardware/${id}`);
    await page.locator(`a[href$="/hardware/${id}/checkout"]`).first().click();
    await choose(page, 'assigned_user', student.option, student.name);
    if (changedStatus) {
      await choose(page, 'status_id', fixtures.other.name);
    }
    await submitForm(page, 'checkout');
    await expect(page.getByText(/asset checked out successfully/i)).toBeVisible();
    const saved = await api(request, 'get', id);
    expect(saved.assigned_to.id).toBe(student.id);
    expect(saved.status.id).toBe(changedStatus ? fixtures.other.id : fixtures.ready.id);
  });
}

for (const scenario of ['checkout-loaned', 'checkout-repair']) {
  test(`UC checkout from Hardware Assets exception: ${scenario}`, async ({ page, request }) => {
    const id = fixtures.cases[scenario];
    const before = await api(request, 'get', id);
    await signIn(page);
    await page.goto(`/hardware/${id}/checkout`);
    await expect(page).toHaveURL(/\/hardware$/);
    await expect(page.locator('#checkout_form')).toHaveCount(0);
    const after = await api(request, 'get', id);
    expect(after.assigned_to).toEqual(before.assigned_to);
    expect(after.status.id).toBe(before.status.id);
    expect(after.checkout_counter).toBe(before.checkout_counter);
  });
}

for (const scenario of ['return-main', 'return-status', 'return-note']) {
  test(`UC return laptop to service: ${scenario}`, async ({ page, request }) => {
    const id = fixtures.cases[scenario];
    const status = scenario === 'return-status' ? fixtures.other : fixtures.ready;
    const note = 'SQE browser return note';
    await signIn(page);
    await page.goto(`/hardware/${id}/checkin`);
    await choose(page, 'status_id', status.name);
    if (scenario === 'return-note') {
      await page.locator('textarea[name="note"]').fill(note);
    }
    await submitForm(page, 'checkin');
    await expect(page.getByText(/asset checked in successfully/i)).toBeVisible();
    const saved = await api(request, 'get', id);
    expect(saved.assigned_to).toBeNull();
    expect(saved.expected_checkin).toBeNull();
    expect(saved.status.id).toBe(status.id);
    expect(saved.available_actions.checkout).toBe(true);
    if (scenario === 'return-note') {
      const history = await api(request, 'get', `${id}/history`);
      expect(history.rows.some(row => row.note === note)).toBe(true);
    }
  });
}

test('UC return laptop to service exception: stale form', async ({ page, request }) => {
  const id = fixtures.cases['return-stale'];
  await signIn(page);
  await page.goto(`/hardware/${id}/checkin`);
  await choose(page, 'status_id', fixtures.ready.name);
  const completed = await api(request, 'post', `${id}/checkin`, { data: { status_id: fixtures.ready.id } });
  expect(completed.status).toBe('success');
  const before = await api(request, 'get', id);
  await submitForm(page, 'checkin');
  await expect(page).toHaveURL(/\/hardware$/);
  const after = await api(request, 'get', id);
  expect(after.assigned_to).toBeNull();
  expect(after.checkin_counter).toBe(before.checkin_counter);
});

test('UC return laptop to service exception: read-only reviewer', async ({ page, request }) => {
  const id = fixtures.cases['return-reviewer'];
  const before = await api(request, 'get', id);
  await signIn(page, fixtures.reviewer);
  await page.goto(`/hardware/${id}`);
  await expect(page.locator(`a[href$="/hardware/${id}/checkin"]`)).toHaveCount(0);
  const response = await page.goto(`/hardware/${id}/checkin`);
  expect(response.status()).toBe(403);
  const after = await api(request, 'get', id);
  expect(after.assigned_to).toEqual(before.assigned_to);
  expect(after.checkin_counter).toBe(before.checkin_counter);
});
