# Usability and accessibility evaluation

Owner: Rafay Imran. All runs were done on 2026-11-25 against the local synthetic instance, signed in as the lab technician, in headless Chromium at 1350×940.
Tools: Playwright 1.61.1, @axe-core/playwright 4.14.1 (axe-core 4.14.1) and Lighthouse 13.6.0 (desktop, no throttling, storage reset off so the session survives).

## 1. Automated usability checks

| Check | Where | Result |
| --- | --- | --- |
| Open the task screen, complete it with test data, confirmation shown | UC-R1-MAIN (checkout), UC-R2-MAIN (checkin) | Pass. "Asset checked out successfully." / "Asset checked in successfully." The saved postcondition is checked through the REST read-back |
| Rejected value, an error that says what to fix, correction, success | UC-R1-EXC1 | Pass. An empty borrower is blocked in the browser: the User row turns red and shows a `role="alert"` message "This field is required". Choosing Sara by keyboard then succeeds |
| Keyboard only: focus order through the required fields and submit, keyboard submit | UC-R1-MAIN | Pass. The test asserts the full Tab order (13 stops). Enter on *Checkout* submits |

Usability findings from these runs:

| ID | Finding | Evidence | Impact | Proposed fix |
| --- | --- | --- | --- | --- |
| U-01 (DEF-R1) | Focusing the empty optional *Expected Checkin Date* fills in the current date and time, and it is saved | DEF-R1 test: `expected_checkin` = the time of the run instead of null | A keyboard user who skips the field records a loan that is due immediately, so overdue reports and reminders are wrong (CO-02) | Root cause in `resources/assets/js/snipeit.js` `initDatetimepicker()`: `data-default-now="false"` is honoured for `defaultDate` but not for eonasdan's `useCurrent`, which defaults to `true`. Set `options.useCurrent = wantsDefaultNow;` |
| U-02 (DEF-R2) | A deleted borrower is rejected, but the message is the raw key `validation.exists_undeleted` | DEF-R2 test, User row text | The technician cannot tell what to fix | Add `'exists_undeleted' => 'The selected :attribute no longer exists. Choose another.'` to `resources/lang/en-US/validation.php` |
| U-03 | A server-side check-in rejection (256-character name) redirects to the asset list, and the status and note the technician entered are lost | UC-R2-EXC1b, URL `/hardware` | The work must be redone, and the error is shown away from the field | In `AssetCheckinController::store()`, return `redirect()->back()->withInput()` with the errors instead of `route('hardware.index')` |
| U-04 | `maxlength=255` drops the 256th character without telling the user | UC-R2-EXC1 | The name is silently shortened. Low impact, because the stored value is at the limit | Optionally show a character counter or a hint about the 255-character limit |
| U-05 | The client-side message "This field is required" does not name the field. The field is identified only by its position and the red label | UC-R1-EXC1 | Screen-reader users hear the alert without the field name | Include the label in the message, or link it with `aria-describedby` and `aria-invalid` on the select2 control |

## 2. Lighthouse and axe-core: before the fix

Screens: the login page, the checkout form (UC-R1 key screen) and the checkin form (UC-R2 key screen).
Raw reports: `evidence/a11y/before/` (`axe-*.json`, `lighthouse-*.json` / `.html`, and the two summaries).

| Screen | Lighthouse a11y / best practices / SEO | axe: serious rules (nodes) |
| --- | --- | --- |
| Login | 96 / 100 / 54 | 1 (1) |
| Checkout | **87** / 100 / 50 | **4 (23)** |
| Checkin | 87 / 100 / 50 | 4 (21) |

### Deduplicated findings (an issue found by both tools is counted once)

| ID | Rule (axe = Lighthouse audit) | Element | Screens | User impact | Proposed fix | Status |
| --- | --- | --- | --- | --- | --- | --- |
| A11Y-01 | label (manual: neither tool flags it, because the placeholder supplies a name) | Login `<label for="password">` vs `<input id="password-field">` | Login | Clicking the "Password" label does not focus the field. Screen readers use the placeholder instead of the label | `for="password-field"` in `resources/views/auth/login.blade.php` | Open (proposed) |
| A11Y-02 | aria-input-field-name, found by both | select2 `span.select2-selection__rendered[role=textbox]` for Status, User, Location, Default Location and After saving | Checkout (5), Checkin (4) | Screen readers announce "edit text, read only" with no field name | Name each picker from its visible `<label>` | **Fixed on checkout** |
| A11Y-03 | color-contrast, found by both | select2 placeholders "Select a User" / "Select a Location" (#999 on white, 2.84:1) | Checkout (3), Checkin (2) | Low-vision users cannot read the hint | Placeholder colour #6b6b6b (5.33:1) | **Fixed on checkout** |
| A11Y-04 | label-in-name (manual; WCAG 2.5.3) | "Asset Name" input with `aria-label="name"` | Checkout, Checkin | Voice-control users say "Asset Name", but the control's name is "name" | Remove the `aria-label` so the visible label is used | **Fixed on checkout** |
| A11Y-05 | link-name, found by both | Collapsed-sidebar links (Calendar, Pending Requests, Unaccepted Items and two menu toggles) | All authenticated screens | The link text is `display:none`, so the links have no name | Keep the text visually hidden but in the accessibility tree | **Fixed (layout)** |
| A11Y-06 | color-contrast, found by both | Header logo, signed-in user name and footer labels (white on #3c8dbc, 3.67:1) | All authenticated screens | Hard to read for low-vision users | Branding setting *Header Color* #296282 (6.64:1). This is configuration, not code | **Fixed (configuration)** |
| A11Y-07 | link-in-text-block, found by both | Footer credit link "Snipe-IT" | All authenticated screens | Distinguished by colour only | Underline text links in `.footer-links` | **Fixed (layout)** |
| A11Y-08 | link-name, found by both | Home breadcrumb icon and four footer social icons | All authenticated screens | Announced as "link" with no destination | `sr-only` crumb title and `aria-label` on the icons | **Fixed (layout)** |
| A11Y-09 | color-contrast, found by both | Login button `btn-primary` (white on #3c8dbc, 3.66:1) | Login | Hard to read | Use the header colour for `btn-primary` in `layouts/basic.blade.php` | Open |
| SEO-01 | meta-description, is-crawlable (Lighthouse only) | No `<meta name="description">`; `public/robots.txt` is `User-agent: * / Disallow: /` | All | None for an internal, sign-in-only tool. Not being indexed is intended | Accepted, no change |
| SEO-02 | crawlable-anchors (Lighthouse only) | Sidebar menu toggles `href="#"` | Authenticated | None for users. Crawlers are not a goal | Accepted |

## 3. The fix: checkout screen

Commit `Fix accessibility failures on the asset checkout screen` touches the following:

* `resources/views/hardware/checkout.blade.php`: a screen-scoped script names every select2 picker from its visible label, removes the stray `aria-label="name"`, and sets the placeholder colour (A11Y-02/03/04).
* `resources/views/blade/redirect_submit_options.blade.php` and `resources/lang/en-US/general.php`: the "after saving" picker gets an `aria-label` from a new key, `general.after_submit`.
* `resources/views/layouts/default.blade.php`: sidebar text kept for assistive technology, an `sr-only` home crumb, `aria-label` on the footer icons and underlined footer text links (A11Y-05/07/08).
* Configuration: `tests/team/playwright/rafay/a11y/set_header_color.sh` sets the *Header Color* branding setting to #296282 (A11Y-06). Passing `NULL` restores the "before" state.

The root-cause fix for A11Y-02/04 belongs in the shared select2 initialisation (`snipeit.js`) and in the shared `x-form.field` component. That needs a Laravel Mix rebuild of `public/js/dist/all.js` and affects every form, so it is proposed for team triage rather than done here.

## 4. After the fix: same tools, same viewport, same seeded laptops, same machine

Raw reports: `evidence/a11y/after/`.

| Screen | Lighthouse a11y before → after | axe serious rules (nodes) before → after |
| --- | --- | --- |
| **Checkout (fixed screen)** | **87 → 100** | **4 (23) → 0 (0)** |
| Checkin (side effect of the layout fixes) | 87 → 93 | 4 (21) → 2 (6) |
| Login (not in scope) | 96 → 96 | 1 (1) → 1 (1) |

Remaining findings, explained:

* **Checkin** keeps A11Y-02 (4 select2 pickers) and A11Y-03 (2 placeholders). The screen-scoped fix was applied only to checkout. The same 20 lines would fix checkin, or the shared fix proposed above would fix both.
* **Login** keeps A11Y-09: the login page uses `layouts/basic.blade.php`, where the button colour does not follow the branding setting. The label mismatch A11Y-01 is also still open there.
* **SEO** stays at 50–54 by design. The tool is internal and sign-in only, and blocking indexing is correct.

## 5. How to reproduce

```bash
cd tests/team/playwright
bash rafay/a11y/set_header_color.sh NULL              # "before" configuration (and check out the commit before the fix)
SQE_A11Y_LABEL=before npx playwright test --project=a11y
SQE_A11Y_LABEL=before node rafay/a11y/lighthouse.mjs
bash rafay/a11y/set_header_color.sh                   # "after" configuration, on the fix commit
php artisan view:clear                                # from the repository root
SQE_A11Y_LABEL=after npx playwright test --project=a11y
SQE_A11Y_LABEL=after node rafay/a11y/lighthouse.mjs
```
