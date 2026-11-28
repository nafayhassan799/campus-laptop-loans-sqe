// UC-R1  Complete student checkout using the keyboard            (owner: Rafay Imran)
//
// Actor: lab technician (assets.view, assets.checkout, assets.checkin).
// Precondition: the laptop is unassigned and has the deployable status "SQE Ready to Deploy".
// Postcondition (success): the same asset record stores the student and the due date, shows as
// deployed, and the history gains exactly one checkout event. (Rejected): nothing changes.
// Requirements: CO-01, CO-02, CO-03; usability (task, error correction, keyboard); access (role).
const s = require('../support/fixtures.cjs');
const { test, expect, data } = s;

const SUCCESS = /asset checked out successfully/i;
const due = (days) => new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 10);

/** The expected keyboard order through the checkout form's controls. */
const FORM_ORDER = ['#name', 'select2:status_id', '#requestable', 'input[name=checkout_to_type]',
  'select2:assigned_user', 'select2:location_id', 'select2:rtd_location_id', '#checkout_at',
  '#expected_checkin', '#note', 'link:Cancel', 'select2:redirect_option', '#submit_button'];

async function openCheckout(page, id) {
  await page.goto(`/hardware/${id}/checkout`);
  await expect(page.getByRole('heading', { name: /asset tag/i })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Checkout' })).toBeVisible();
}

/** Keyboard only: replace whatever the due-date field holds with `date`, then close the picker. */
async function typeDueDate(page, date) {
  await page.keyboard.press('ControlOrMeta+a');
  await page.keyboard.type(`${date} 17:00:00`);
  await page.keyboard.press('Escape');
}

/** Keyboard only from the top of the page to the borrower picker, choosing one student. */
async function keyboardToBorrower(page, search, option) {
  await s.tabTo(page, 'select2:assigned_user');
  await s.keyboardChoose(page, search, option);
}

const unchanged = (before, after) => {
  expect(after.assigned_to).toEqual(before.assigned_to);
  expect(after.expected_checkin).toEqual(before.expected_checkin);
  expect(after.status_label).toEqual(before.status_label);
  expect(after.checkout_counter).toBe(before.checkout_counter);
};

test.describe('UC-R1 keyboard checkout', () => {
  test('UC-R1-MAIN keyboard reaches the borrower and submit in order, checks out, and the loan is saved [CO-01 CO-02 USAB-KBD USAB-TASK]',
    async ({ technician: page, request }) => {
      const id = data.assets['RAF-CO-MAIN'];
      const sara = data.students[0];
      const before = await s.resetAsset(request, id);
      const events = await s.history(request, id);
      await openCheckout(page, id);

      // Focus order from the top of the page: every form control in the documented order.
      const walked = await s.tabTo(page, 'select2:assigned_user');
      const formPart = walked.slice(walked.indexOf('#name'));
      expect(formPart).toEqual(FORM_ORDER.slice(0, FORM_ORDER.indexOf('select2:assigned_user') + 1));
      await s.keyboardChoose(page, 'Sara', `${sara.name} (${sara.username})`);
      await expect(page.locator('select[name="assigned_user"]')).toHaveValue(String(sara.id));

      const rest = await s.tabTo(page, '#expected_checkin');
      expect(rest).toEqual(['select2:location_id', 'select2:rtd_location_id', '#checkout_at', '#expected_checkin']);
      await typeDueDate(page, due(14));
      expect(await s.tabTo(page, '#submit_button')).toEqual(FORM_ORDER.slice(FORM_ORDER.indexOf('#note')));
      await page.keyboard.press('Enter');

      await expect(s.flash(page).filter({ hasText: SUCCESS })).toBeVisible();
      const saved = await s.readAsset(request, id);
      expect(saved.assigned_to.id).toBe(sara.id);
      expect(saved.expected_checkin.datetime).toMatch(new RegExp(`^${due(14)}`));
      expect(saved.status_label.status_meta).toBe('deployed');
      expect(saved.checkout_counter).toBe(before.checkout_counter + 1);
      expect(s.countActions(await s.history(request, id), 'checkout')).toBe(s.countActions(events, 'checkout') + 1);
    });

  test('UC-R1-ALT1 a note typed with the keyboard is saved with the checkout [CO-01]', async ({ technician: page, request }) => {
    const id = data.assets['RAF-CO-ALT1'];
    const note = `Charger and sleeve lent with laptop ${Date.now()}`;
    await s.resetAsset(request, id);
    await openCheckout(page, id);

    await keyboardToBorrower(page, 'Sara', `${data.students[0].name} (${data.students[0].username})`);
    await s.tabTo(page, '#expected_checkin');
    await typeDueDate(page, due(7));
    await s.tabTo(page, '#note');
    await page.keyboard.type(note);
    await s.tabTo(page, '#submit_button');
    await page.keyboard.press('Enter');

    await expect(s.flash(page).filter({ hasText: SUCCESS })).toBeVisible();
    const saved = await s.readAsset(request, id);
    expect(saved.assigned_to.id).toBe(data.students[0].id);
    const checkouts = (await s.history(request, id)).filter((event) => event.action === 'checkout');
    expect(checkouts.at(-1).note).toBe(note);
  });

  test('UC-R1-ALT2 keyboard search narrows the results and arrow keys pick another eligible borrower [CO-01]',
    async ({ technician: page, request }) => {
      const id = data.assets['RAF-CO-ALT2'];
      const ali = data.students[1];
      await s.resetAsset(request, id);
      await openCheckout(page, id);

      await s.tabTo(page, 'select2:assigned_user');
      await page.keyboard.press('Enter');
      const open = page.locator('.select2-container--open');
      // Wait for select2 to move focus into its search box, or the first keystrokes are lost.
      await expect(open.locator('.select2-search__field')).toBeFocused();
      await page.keyboard.type('sqe_student');
      await expect(open.locator('.select2-search__field')).toHaveValue('sqe_student');
      // Both seeded students match the search; the list is sorted by name, so Ali comes first.
      await expect(open.getByRole('option')).toHaveText(
        [...data.students].sort((a, b) => a.name.localeCompare(b.name)).map((st) => `${st.name} (${st.username})`));
      for (let i = 0; i < 5; i++) {
        if ((await open.locator('.select2-results__option--highlighted').innerText()).includes(ali.username)) { break; }
        await page.keyboard.press('ArrowDown');
      }
      await expect(open.locator('.select2-results__option--highlighted')).toHaveText(`${ali.name} (${ali.username})`);
      await page.keyboard.press('Enter');
      await s.tabTo(page, '#expected_checkin');
      await typeDueDate(page, due(3));
      await s.tabTo(page, '#submit_button');
      await page.keyboard.press('Enter');

      await expect(s.flash(page).filter({ hasText: SUCCESS })).toBeVisible();
      const saved = await s.readAsset(request, id);
      expect(saved.assigned_to.id).toBe(ali.id);
      expect(saved.expected_checkin.datetime).toMatch(new RegExp(`^${due(3)}`));
    });

  test('UC-R1-EXC1 submitting without a borrower is rejected with a message saying what to fix, then the corrected form succeeds [CO-01 CO-03 USAB-ERR]',
    async ({ technician: page, request }) => {
      const id = data.assets['RAF-CO-EXC1'];
      const before = await s.resetAsset(request, id);
      await openCheckout(page, id);

      // Rejected attempt: the technician tabs straight to Checkout without choosing a student.
      const posts = [];
      page.on('request', (req) => { if (req.method() === 'POST' && req.url().includes('/checkout')) { posts.push(req.url()); } });
      await s.tabTo(page, '#submit_button');
      await page.keyboard.press('Enter');
      // The form's validator stops the submission and says, inside the User row, what is missing.
      const userRow = page.locator('.form-group').filter({ has: page.locator('select[name="assigned_user"]') });
      await expect(userRow).toHaveClass(/has-error/);
      await expect(userRow.getByRole('alert')).toHaveText('This field is required');
      await expect(userRow.locator('label').first()).toHaveText(/user/i);
      await expect(page).toHaveURL(new RegExp(`/hardware/${id}/checkout$`));
      await expect(s.flash(page).filter({ hasText: SUCCESS })).toHaveCount(0);
      expect(posts).toEqual([]);
      unchanged(before, await s.readAsset(request, id));

      // Correction through the same form, keyboard only.
      await page.locator('#name').focus();
      await keyboardToBorrower(page, 'Sara', `${data.students[0].name} (${data.students[0].username})`);
      await s.tabTo(page, '#expected_checkin');
      await typeDueDate(page, due(10));
      await s.tabTo(page, '#submit_button');
      await page.keyboard.press('Enter');
      await expect(s.flash(page).filter({ hasText: SUCCESS })).toBeVisible();
      const saved = await s.readAsset(request, id);
      expect(saved.assigned_to.id).toBe(data.students[0].id);
      expect(saved.checkout_counter).toBe(before.checkout_counter + 1);
      expect(posts).toHaveLength(1);
    });

  test('UC-R1-EXC2 a read-only reviewer cannot make the same checkout and nothing is saved [ROLE CO-03]',
    async ({ reviewer: page, request }) => {
      const id = data.assets['RAF-CO-EXC2'];
      const before = await s.resetAsset(request, id);

      await page.goto(`/hardware/${id}`);
      await expect(page.getByText(`RAF-CO-EXC2`).first()).toBeVisible();
      await expect(page.locator(`a[href$="/hardware/${id}/checkout"]`)).toHaveCount(0);
      const form = await page.goto(`/hardware/${id}/checkout`);
      expect(form.status()).toBe(403);
      await expect(page.locator('#checkout_form')).toHaveCount(0);

      // The same submission the technician makes, sent with the reviewer's own session and CSRF token.
      await page.goto(`/hardware/${id}`);
      const token = await page.locator('meta[name="csrf-token"]').getAttribute('content');
      const post = await page.request.post(`/hardware/${id}/checkout`, {
        form: { _token: token, checkout_to_type: 'user', assigned_user: String(data.students[0].id), status_id: String(data.status.ready.id) },
        maxRedirects: 0,
      });
      expect(post.status()).toBe(403);
      unchanged(before, await s.readAsset(request, id));
    });
});

test.describe('UC-R1 checkout regressions', () => {
  test('DEF-R1 tabbing past an optional due date leaves it empty [CO-02]',
    async ({ technician: page, request }) => {
      const id = data.assets['RAF-CO-MAIN'];
      await s.resetAsset(request, id);
      await openCheckout(page, id);
      await expect(page.locator('#expected_checkin')).toHaveValue('');
      await keyboardToBorrower(page, 'Sara', `${data.students[0].name} (${data.students[0].username})`);

      await s.tabTo(page, '#submit_button'); // passes through "Expected Checkin Date" without typing
      await expect(page.locator('#expected_checkin')).toHaveValue('');
      await page.keyboard.press('Enter');
      await expect(s.flash(page).filter({ hasText: SUCCESS })).toBeVisible();
      const saved = await s.readAsset(request, id);
      expect(saved.assigned_to.id).toBe(data.students[0].id);

      expect(saved.expected_checkin).toBeNull();
    });

  test('DEF-R2 a borrower removed before submit gets a useful error [CO-01 USAB-ERR]',
    async ({ technician: page, request }) => {
      const id = data.assets['RAF-CO-EXC1'];
      const before = await s.resetAsset(request, id);
      const username = `sqe_student_leaver_${Date.now()}`;
      const created = await s.call(request, 'admin', 'POST', 'users',
        { username, first_name: 'Leaver', last_name: 'SQE', password: 'Leaver-only-local-1!', password_confirmation: 'Leaver-only-local-1!' });
      expect(created.status).toBe('success');
      await openCheckout(page, id);
      await s.choose(page, 'assigned_user', `Leaver SQE (${username})`, 'Leaver');
      await expect(page.locator('select[name="assigned_user"]')).toHaveValue(String(created.payload.id));
      expect((await s.call(request, 'admin', 'DELETE', `users/${created.payload.id}`)).status).toBe('success');
      await page.getByRole('button', { name: 'Checkout' }).click();

      // The rule holds: back on the same form, the User row is flagged, and nothing was saved.
      await expect(page).toHaveURL(new RegExp(`/hardware/${id}/checkout$`));
      await expect(s.flash(page).filter({ hasText: /check the form below for errors/i })).toBeVisible();
      const userRow = page.locator('.form-group.has-error').filter({ has: page.locator('select[name="assigned_user"]') });
      await expect(userRow).toBeVisible();
      unchanged(before, await s.readAsset(request, id));

      const message = (await userRow.locator('.alert-msg, .help-block, [role="alert"]').allInnerTexts()).join(' ').trim();
      expect(message).toMatch(/no longer exists\. Choose another\./);
    });
});
