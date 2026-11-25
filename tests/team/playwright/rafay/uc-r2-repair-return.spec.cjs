// UC-R2  Return a damaged laptop for repair                       (owner: Rafay Imran)
//
// Actor: lab technician.
// Precondition: the laptop is checked out to student Sara with a due date (set through the API).
// Postcondition (success): borrower and due date are cleared, the chosen non-deployable status is
// kept, the laptop cannot be lent again, and the history gains exactly one return event.
// Requirements: CI-01, CI-03, CO-04 (name limit on the return form), CO-03 (no loan while in repair).
const s = require('../support/fixtures.cjs');
const { test, expect, data } = s;

const RETURNED = /asset checked in successfully/i;
const NOT_AVAILABLE = 'That asset is not available for checkout!';
const returns = (events) => s.countActions(events, 'checkin from');

async function openCheckin(page, id) {
  await page.goto(`/hardware/${id}/checkin`);
  await expect(page).toHaveTitle(/checkin asset/i);
  await expect(page.getByRole('button', { name: /checkin/i })).toBeVisible();
}

/** Borrower and due date gone, status kept, not lendable: the saved state after a repair return. */
async function expectUnavailableReturn(request, id, status, before) {
  const saved = await s.readAsset(request, id);
  expect(saved.assigned_to).toBeNull();
  expect(saved.expected_checkin).toBeNull();
  expect(saved.status_label.id).toBe(status.id);
  expect(saved.status_label.status_meta).not.toBe('deployable');
  // user_can_checkout mirrors Asset::availableForCheckout(); available_actions.checkout is only the caller's permission.
  expect(saved.user_can_checkout).toBe(false);
  expect(saved.checkin_counter).toBe(before.checkin_counter + 1);
  return saved;
}

test.describe('UC-R2 repair return', () => {
  test('UC-R2-MAIN returning with the repair status clears borrower and due date and the laptop stays unavailable [CI-01 CI-03 USAB-TASK]',
    async ({ technician: page, request }) => {
      const id = data.assets['RAF-CI-MAIN'];
      const before = await s.loanAsset(request, id);
      const events = await s.history(request, id);
      await openCheckin(page, id);
      await expect(page.getByText(data.students[0].name).first()).toBeVisible(); // "checked out to" panel

      await s.choose(page, 'status_id', data.status.repair.name);
      await page.waitForLoadState('networkidle');
      await page.getByRole('button', { name: /checkin/i }).click();

      await expect(s.flash(page).filter({ hasText: RETURNED })).toBeVisible();
      await expectUnavailableReturn(request, id, data.status.repair, before);
      expect(returns(await s.history(request, id))).toBe(returns(events) + 1);
      // Separate browser read: the record page shows the repair status and offers no checkout.
      await page.goto(`/hardware/${id}`);
      await expect(page.locator('body')).toContainText(data.status.repair.name);
      await expect(page.locator(`a[href$="/hardware/${id}/checkout"]`)).toHaveCount(0);
    });

  test('UC-R2-ALT1 a separate pending-assessment status is kept and the laptop stays unavailable [CI-01 CI-03]',
    async ({ technician: page, request }) => {
      const id = data.assets['RAF-CI-ALT1'];
      const before = await s.loanAsset(request, id);
      await openCheckin(page, id);

      await s.choose(page, 'status_id', data.status.pending.name);
      await page.waitForLoadState('networkidle');
      await page.getByRole('button', { name: /checkin/i }).click();

      await expect(s.flash(page).filter({ hasText: RETURNED })).toBeVisible();
      const saved = await expectUnavailableReturn(request, id, data.status.pending, before);
      expect(saved.status_label.status_meta).toBe('pending');
    });

  test('UC-R2-ALT2 a damage note is saved with the return and shown in the record history [CI-01]',
    async ({ technician: page, request }) => {
      const id = data.assets['RAF-CI-ALT2'];
      const note = `Cracked hinge and sticky trackpad, reported at return ${Date.now()}`;
      const before = await s.loanAsset(request, id);
      await openCheckin(page, id);

      await s.choose(page, 'status_id', data.status.repair.name);
      await page.getByRole('textbox', { name: 'Notes' }).fill(note);
      await page.waitForLoadState('networkidle');
      await page.getByRole('button', { name: /checkin/i }).click();

      await expect(s.flash(page).filter({ hasText: RETURNED })).toBeVisible();
      await expectUnavailableReturn(request, id, data.status.repair, before);
      const lastReturn = (await s.history(request, id)).filter((event) => event.action === 'checkin from').at(-1);
      expect(lastReturn.note).toBe(note);
      // The same note in the History tab of the asset page.
      await page.goto(`/hardware/${id}#history`);
      await expect(page.locator('#history')).toContainText(note);
    });

  test('UC-R2-EXC1 an over-limit asset name on the return form is capped at 255 characters by the form [CO-04]',
    async ({ technician: page, request }) => {
      const id = data.assets['RAF-CI-EXC1'];
      const before = await s.loanAsset(request, id);
      await openCheckin(page, id);
      const name = page.locator('#name');
      await expect(name).toHaveAttribute('maxlength', '255');

      await name.fill('');
      await name.pressSequentially('R'.repeat(256), { delay: 0 }); // typing one character past the limit
      await expect(name).toHaveValue('R'.repeat(255)); // the 256th keystroke is dropped, without any message
      await s.choose(page, 'status_id', data.status.repair.name);
      await page.waitForLoadState('networkidle');
      await page.getByRole('button', { name: /checkin/i }).click();

      await expect(s.flash(page).filter({ hasText: RETURNED })).toBeVisible();
      const saved = await expectUnavailableReturn(request, id, data.status.repair, before);
      expect(saved.name).toBe('R'.repeat(255)); // exactly at the limit, stored in full (no 191 truncation)
    });

  test('UC-R2-EXC1b a 256-character name that reaches the server is rejected and the loan is left intact [CO-04 CI-01]',
    async ({ technician: page, request }) => {
      // A client that does not apply maxlength (older browser, script, or a pasted autofill) still
      // reaches the server rule. This is the server-side half of how the form handles the limit.
      const id = data.assets['RAF-CI-EXC1'];
      const before = await s.loanAsset(request, id);
      const events = await s.history(request, id);
      await openCheckin(page, id);
      await page.locator('#name').evaluate((input) => input.removeAttribute('maxlength'));
      await page.locator('#name').fill('R'.repeat(256));
      await s.choose(page, 'status_id', data.status.repair.name);
      await page.waitForLoadState('networkidle');
      await page.getByRole('button', { name: /checkin/i }).click();

      await expect(s.flash(page).filter({ hasText: 'Asset was not checked in, please try again' })).toBeVisible();
      await expect(s.flash(page).filter({ hasText: 'The name field must not be greater than 255 characters.' })).toBeVisible();
      await expect(page).toHaveURL(/\/hardware$/); // finding U-03: back on the list, the form input is lost
      const after = await s.readAsset(request, id);
      expect(after.assigned_to.id).toBe(data.students[0].id);
      expect(after.expected_checkin).toEqual(before.expected_checkin);
      expect(after.status_label.id).toBe(before.status_label.id);
      expect(after.checkin_counter).toBe(before.checkin_counter);
      expect(returns(await s.history(request, id))).toBe(returns(events));
    });

  test('UC-R2-EXC2 lending the laptop after a repair return is refused and the unassigned repair state is kept [CI-03 CO-03]',
    async ({ technician: page, request }) => {
      const id = data.assets['RAF-CI-EXC2'];
      await s.loanAsset(request, id);
      const returned = await s.call(request, 'admin', 'POST', `hardware/${id}/checkin`, { status_id: data.status.repair.id });
      expect(returned.status).toBe('success');
      const before = await s.readAsset(request, id);

      await page.goto(`/hardware/${id}`);
      await expect(page.locator(`a[href$="/hardware/${id}/checkout"]`)).toHaveCount(0);
      await page.goto(`/hardware/${id}/checkout`); // e.g. a bookmarked or shared checkout link
      await expect(page).toHaveURL(/\/hardware$/);
      await expect(s.flash(page).filter({ hasText: NOT_AVAILABLE })).toBeVisible();
      await expect(page.locator('#checkout_form')).toHaveCount(0);

      const after = await s.readAsset(request, id);
      expect(after.assigned_to).toBeNull();
      expect(after.status_label.id).toBe(data.status.repair.id);
      expect(after.checkout_counter).toBe(before.checkout_counter);
      expect(after.user_can_checkout).toBe(false);
    });
});
