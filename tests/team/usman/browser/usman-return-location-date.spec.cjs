// Use case 2: record the return location and date while checking a laptop back in.
const { test, expect } = require('@playwright/test');
const s = require('./support.cjs');

async function loanedAsset(request, tag, { checkoutAt, rtdLocation } = {}) {
  const id = await s.ensureAsset(request, tag);
  await s.resetAsset(request, id);
  await s.call(request, 'admin', 'PATCH', `hardware/${id}`, { rtd_location_id: rtdLocation || null });
  const body = { checkout_to_type: 'user', assigned_user: s.data.students[0].id, expected_checkin: s.addDays(7) };
  if (checkoutAt) { body.checkout_at = checkoutAt; }
  const result = await s.call(request, 'technician', 'POST', `hardware/${id}/checkout`, body);
  expect(result.status, JSON.stringify(result)).toBe('success');
  return { id, events: await s.history(request, id), asset: await s.readAsset(request, id) };
}

async function openCheckin(page, id) {
  await s.signIn(page);
  await page.goto(`/hardware/${id}/checkin`);
  await expect(page.getByRole('heading', { name: /checkin asset/i })).toBeVisible();
}

const returns = (events) => events.filter((e) => e.action === 'checkin from');
const submitCheckin = (page) => s.submit(page, 'checkin');

test.describe('UC2 record the return location and date', () => {
  test('UC2-MAIN technician returns a laptop to a chosen location and the return record shows it', async ({ page, request }) => {
    const { id, events, asset } = await loanedAsset(request, 'BR-CI-01');
    await openCheckin(page, id);
    await s.choose(page, 'status_id', s.data.ready.name);
    await s.choose(page, 'location_id', s.data.location.name, 'Return Desk');
    await page.locator('#note').fill('Returned at the desk');
    await submitCheckin(page);

    await expect(page.getByText(/asset checked in successfully/i)).toBeVisible();
    const saved = await s.readAsset(request, id);
    expect(saved.assigned_to).toBeNull();
    expect(saved.expected_checkin).toBeNull();
    expect(saved.location.id).toBe(s.data.location.id);
    expect(saved.status.id).toBe(s.data.ready.id);
    expect(saved.checkin_counter).toBe(asset.checkin_counter + 1);
    const after = await s.history(request, id);
    expect(returns(after)).toHaveLength(returns(events).length + 1);
    await page.goto(`/hardware/${id}`);
    await expect(page.locator('body')).toContainText(s.data.location.name);
  });

  test('UC2-ALT1 keeping the default return location sends the laptop to its default location', async ({ page, request }) => {
    const { id, events, asset } = await loanedAsset(request, 'BR-CI-02', { rtdLocation: s.data.locationTwo.id });
    await openCheckin(page, id);
    await expect(page.locator('select[name="location_id"]')).toHaveValue(String(s.data.locationTwo.id)); // pre-filled
    await s.choose(page, 'status_id', s.data.ready.name);
    await submitCheckin(page);

    await expect(page.getByText(/asset checked in successfully/i)).toBeVisible();
    const saved = await s.readAsset(request, id);
    expect(saved.assigned_to).toBeNull();
    expect(saved.location.id).toBe(s.data.locationTwo.id);
    expect(saved.checkin_counter).toBe(asset.checkin_counter + 1);
    expect(returns(await s.history(request, id))).toHaveLength(returns(events).length + 1);
  });

  test('UC2-ALT2 a supported earlier return date is recorded in the history', async ({ page, request }) => {
    const earlier = s.addDays(-3);
    const { id, events } = await loanedAsset(request, 'BR-CI-03', { checkoutAt: `${s.addDays(-5)} 09:00:00` });
    await openCheckin(page, id);
    await s.choose(page, 'status_id', s.data.ready.name);
    await page.locator('#checkin_at').fill(`${earlier} 10:30:00`);
    await page.locator('#note').click();
    await expect(page.locator('#checkin_at')).toHaveValue(`${earlier} 10:30:00`);
    await submitCheckin(page);

    await expect(page.getByText(/asset checked in successfully/i)).toBeVisible();
    const after = await s.history(request, id);
    const added = returns(after).filter((e) => !returns(events).some((o) => o.id === e.id));
    expect(added).toHaveLength(1);
    expect(added[0].date.slice(0, 10)).toBe(earlier);
    const saved = await s.readAsset(request, id);
    expect(saved.assigned_to).toBeNull();
  });

  test('UC2-EXC1 with check-in notes required, omitting the note blocks the return and nothing is recorded', async ({ page, request }) => {
    const { id, events, asset } = await loanedAsset(request, 'BR-CI-04');
    s.setNotesRequired(true);
    try {
      await openCheckin(page, id);
      await s.choose(page, 'status_id', s.data.ready.name);
      await expect(page.locator('#note')).toHaveAttribute('required', '');
      await submitCheckin(page);

      await expect(page).toHaveURL(new RegExp(`/hardware/${id}/checkin`));
      expect(await page.locator(':invalid').evaluateAll((n) => n.map((x) => x.id))).toContain('note');
      let saved = await s.readAsset(request, id);
      expect(saved.assigned_to.id).toBe(s.data.students[0].id);
      expect(saved.checkin_counter).toBe(asset.checkin_counter);
      expect(returns(await s.history(request, id))).toHaveLength(returns(events).length);

      // Bypass the browser's own check: the server must refuse the empty note too.
      await page.locator('#note').evaluate((n) => n.removeAttribute('required'));
      await submitCheckin(page);
      await expect(page.locator('body')).toContainText(/note/i);
      await expect(page.getByText(/asset checked in successfully/i)).toHaveCount(0);
      saved = await s.readAsset(request, id);
      expect(saved.assigned_to.id).toBe(s.data.students[0].id);
      expect(saved.checkin_counter).toBe(asset.checkin_counter);
      expect(returns(await s.history(request, id))).toHaveLength(returns(events).length);
    } finally {
      s.setNotesRequired(false);
    }
  });

  test('UC2-EXC2 opening a return link for a missing asset shows an error and records no return', async ({ page, request }) => {
    const { id, events, asset } = await loanedAsset(request, 'BR-CI-05');
    await s.signIn(page);
    const response = await page.goto('/hardware/999999/checkin');
    expect(response.status()).toBeLessThan(500);
    await expect(page).not.toHaveURL(/999999\/checkin/);
    await expect(page.locator('body')).toContainText(/does not exist|not found|error/i);
    const missing = await s.call(request, 'admin', 'GET', 'hardware/999999');
    expect(missing.status).toBe('error');
    const saved = await s.readAsset(request, id); // the neighbouring fixture is untouched
    expect(saved.assigned_to.id).toBe(s.data.students[0].id);
    expect(saved.checkin_counter).toBe(asset.checkin_counter);
    expect(returns(await s.history(request, id))).toHaveLength(returns(events).length);
  });
});
