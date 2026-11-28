// Use case 1: record the expected return date while checking a laptop out to a student.
// Actor: lab technician (view + checkout + checkin). Every case owns its own laptop so it can run in
// isolation. Each assertion has two halves: what the technician sees, and what is saved (REST read-back + history).
const { test, expect } = require('@playwright/test');
const s = require('./support.cjs');

const SHAPE = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/;
const dueOf = (asset) => (asset.expected_checkin ? asset.expected_checkin.datetime : null);

async function prepare(request, tag) {
  const id = await s.ensureAsset(request, tag);
  await s.resetAsset(request, id);
  const before = { asset: await s.readAsset(request, id), events: await s.history(request, id) };
  return { id, before };
}

async function openCheckout(page, id, student = 0) {
  await s.signIn(page);
  await page.goto(`/hardware/${id}/checkout`);
  await expect(page.getByRole('heading', { name: /checkout asset/i })).toBeVisible();
  await s.choose(page, 'assigned_user', s.data.students[student].name, s.data.students[student].username);
}

/** Type into the due-date picker the way a person does. Playwright's fill() sets the value without focusing the
 * picker first, which makes the picker discard a perfectly valid date, so keystrokes are used instead. */
async function enterDue(page, text) {
  const field = page.locator('#expected_checkin');
  await field.click();
  await field.press('Control+A');
  await field.pressSequentially(text);
  await page.locator('#note').click(); // leave the field so the picker settles its value
  return field;
}

async function submitCheckout(page) {
  await s.submit(page, 'checkout');
}

test.describe('UC1 record the expected return date during checkout', () => {
  test('UC1-MAIN technician assigns a laptop with a valid due date and the stored date matches', async ({ page, request }) => {
    const { id, before } = await prepare(request, 'BR-CO-01');
    const due = s.addDays(7);
    await openCheckout(page, id);
    // The placeholder asks for YYYY-MM-DD HH:MM:SS. A date alone is also accepted and becomes midnight.
    await enterDue(page, `${due} 12:00:00`);
    await expect(page.locator('#expected_checkin')).toHaveValue(`${due} 12:00:00`);
    await submitCheckout(page);

    await expect(page.getByText(/asset checked out successfully/i)).toBeVisible();
    const saved = await s.readAsset(request, id);
    expect(saved.assigned_to.id).toBe(s.data.students[0].id);
    expect(dueOf(saved).slice(0, 10)).toBe(due);
    expect(saved.status.status_meta.toLowerCase()).toBe('deployed');
    const events = await s.history(request, id);
    expect(s.count(events, 'checkout')).toBe(s.count(before.events, 'checkout') + 1);

    await page.goto(`/hardware/${id}`);
    await expect(page.getByText('Expected Checkin').first()).toBeVisible();
    await expect(page.locator('body')).toContainText(due);
  });

  test('UC1-ALT1 leaving the optional due date blank stores no due date', async ({ page, request }) => {
    const { id, before } = await prepare(request, 'BR-CO-02');
    await openCheckout(page, id);
    await expect(page.locator('#expected_checkin')).toHaveValue('');
    await submitCheckout(page);

    await expect(page.getByText(/asset checked out successfully/i)).toBeVisible();
    const saved = await s.readAsset(request, id);
    expect(saved.assigned_to.id).toBe(s.data.students[0].id);
    expect(saved.expected_checkin).toBeNull();
    expect(s.count(await s.history(request, id), 'checkout')).toBe(s.count(before.events, 'checkout') + 1);
    await page.goto(`/hardware/${id}`);
    await expect(page.locator('body')).not.toContainText(/Expected Checkin\s*\S*\d{4}-\d{2}-\d{2}/);
  });

  test('UC1-ALT2 a different valid due date chosen with the date picker is the date that is saved', async ({ page, request }) => {
    const { id } = await prepare(request, 'BR-CO-03');
    await openCheckout(page, id, 1);
    await page.locator('#expected_checkin').click();
    const widget = page.locator('.bootstrap-datetimepicker-widget').first();
    await expect(widget).toBeVisible();
    await widget.locator('.datepicker-days th.next').click(); // next month
    const day = widget.locator('.datepicker-days td.day:not(.old):not(.new)').nth(14); // the 15th
    await day.click();
    const shown = await page.locator('#expected_checkin').inputValue();
    expect(shown).toMatch(SHAPE);
    expect(shown.slice(0, 10) > s.today(), 'picker date is in the future').toBeTruthy();
    await page.locator('#note').click();
    await submitCheckout(page);

    await expect(page.getByText(/asset checked out successfully/i)).toBeVisible();
    const saved = await s.readAsset(request, id);
    expect(saved.assigned_to.id).toBe(s.data.students[1].id);
    expect(dueOf(saved).slice(0, 10)).toBe(shown.slice(0, 10));
  });

  test('UC1-EXC1 submitting without a borrower is blocked and nothing is saved', async ({ page, request }) => {
    const { id, before } = await prepare(request, 'BR-CO-04');
    await s.signIn(page);
    await page.goto(`/hardware/${id}/checkout`);
    await enterDue(page, s.addDays(7));
    await submitCheckout(page);

    await expect(page).toHaveURL(new RegExp(`/hardware/${id}/checkout`)); // still on the form
    const invalid = await page.locator(':invalid').evaluateAll((nodes) => nodes.map((n) => n.name).filter(Boolean));
    expect(invalid).toContain('assigned_user'); // the browser flags the empty required borrower field
    await expect(page.getByText(/asset checked out successfully/i)).toHaveCount(0);
    const after = await s.readAsset(request, id);
    expect(after.assigned_to).toBeNull();
    expect(after.expected_checkin).toBeNull();
    expect(after.checkout_counter).toBe(before.asset.checkout_counter);
    expect(await s.history(request, id)).toEqual(before.events);
  });

  test('UC1-EXC2 an invalid due date is rejected and can be corrected', async ({ page, request }) => {
    const { id, before } = await prepare(request, 'BR-CO-05');
    await openCheckout(page, id);
    const field = page.locator('#expected_checkin');
    for (const bad of ['not a date', '2026-13-45', '2027-02-29']) {
      await enterDue(page, bad);
      await expect(field).toHaveValue(bad);
    }
    await enterDue(page, 'not a date');
    await submitCheckout(page);
    await expect(page).toHaveURL(new RegExp(`/hardware/${id}/checkout$`));
    await expect(page.locator('.form-group.has-error').filter({ has: field })).toContainText(/valid date/i);
    const unchanged = await s.readAsset(request, id);
    expect(unchanged.assigned_to).toBeNull();
    expect(dueOf(unchanged)).toBeNull();
    expect(unchanged.checkout_counter).toBe(before.asset.checkout_counter);
    expect(await s.history(request, id)).toEqual(before.events);

    const corrected = `${s.addDays(7)} 12:00:00`;
    await enterDue(page, corrected);
    await submitCheckout(page);
    await expect(page.getByText(/asset checked out successfully/i)).toBeVisible();
    const saved = await s.readAsset(request, id);
    expect(saved.assigned_to.id).toBe(s.data.students[0].id);
    expect(dueOf(saved)).toBe(corrected);
  });
});
