# Findings, risk input and traceability (Rafay Imran's area)

This is input to the shared test-management documents. Scores and severities are **proposals for team triage**.
Risks owned by Nafay or Usman are marked "owner to score" and should be confirmed or replaced by them.

## 1. Defects and findings for GitHub Issues

Severity: S1 critical, S2 major, S3 minor, S4 cosmetic. Priority: P1 fix before release, P2 next iteration, P3 backlog.

| ID | Title | Category | Severity / priority (proposed) | Evidence | Root cause (verified in source) | Proposed fix | Linked risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DEF-R1 | Skipping the optional due date with the keyboard saves "now" as the due date | Functional / usability | **S2 / P1** | `DEF-R1` test (`test.fail`), read-back `expected_checkin` = run time | `snipeit.js` `initDatetimepicker()`: `data-default-now="false"` is applied to `defaultDate` only; eonasdan `useCurrent` (default `true`) fills the value when the picker opens on focus (`allowInputToggle: true`) | `options.useCurrent = wantsDefaultNow` and rebuild | PR-02 |
| DEF-R2 | Deleted-borrower rejection shows the raw key `validation.exists_undeleted` | Usability / i18n | S3 / P2 | `DEF-R2` test | The custom rule is registered in `ValidationServiceProvider.php:105`, but no message exists in `resources/lang/en-US/validation.php` | Add the translation | PR-09 |
| U-03 | A server-side check-in rejection redirects to the asset list and loses the input | Usability | S3 / P2 | `UC-R2-EXC1b` | `AssetCheckinController::store()` returns `route('hardware.index')` on a save failure | `back()->withInput()` | PR-09 |
| A11Y-01 | Login "Password" label not tied to its input | Accessibility | S3 / P2 | `login.blade.php:70/76` (`for="password"` vs `id="password-field"`) | Mismatched id | `for="password-field"` | PR-09 |
| A11Y-02…08 | Unnamed pickers, low contrast, unnamed links on the checkout screen | Accessibility | S3 / P2 | `evidence/a11y/before/` | See `usability-accessibility.md` | **Fixed on checkout and verified** (Lighthouse 87 → 100, axe 4 → 0 rules) | PR-09 |
| A11Y-02/03 (checkin) | The same picker and placeholder issues remain on checkin | Accessibility | S3 / P2 | `evidence/a11y/after/axe-checkin.json` | Screen-scoped fix not applied there | Apply the same script, or the shared `snipeit.js` fix | PR-09 |
| SEC-01 | CSP allows `unsafe-inline` / `unsafe-eval` | Security | S3 / P2 | ZAP 10055, `SecurityHeaders.php:84-86` | Policy predates nonce use | Per-response nonce | PR-07 |
| SEC-02 | Bootstrap 3.3.4 JS shipped through `bootstrap-less` | Security / dependency | S2 / P2 | ZAP 10003, source map, `snipeit.js:16` | Wrong package required; npm audit cannot see it | `require('bootstrap')` | PR-07 |
| SEC-03 / SEC-04 | No `Secure` flag; 8.3-day idle session | Security / configuration | S2 / P1 for any HTTPS deployment | Set-Cookie (ZAP), `config/session.php:40,159`, `.env` | Defaults | `SECURE_COOKIES=true`, `SESSION_LIFETIME=30`, `EXPIRE_ON_CLOSE=true` | PR-08 |
| SEC-05…07, D-01, D-03, D-04 | See `security-assessment.md` §7 | Security | S3–S4 / P3 | n/a | n/a | n/a | PR-07, PR-05 |
| TEST-01 | Nafay's return tests treat `available_actions.checkout === true` as "available again" (CI-02) | Weak assertion (test defect) | n/a, raise with Nafay | `nafay-loans.spec.cjs` on `sqe/nafay-quality`; transformer `AssetsTransformer.php:170` is permission-only and is `true` for a laptop in repair | `available_actions` reports the caller's permission, not eligibility | Also assert `user_can_checkout === true` (line 153: `availableForCheckout()`) | PR-06 |

### Root cause analysis for a major defect: DEF-R1

**5 Whys**
1. Why did the loan get a due date of "now"? The *Expected Checkin Date* input held the current time when the form was submitted.
2. Why did it hold the current time? The eonasdan date picker writes a date into an empty input when its popup opens.
3. Why did the popup open? `allowInputToggle: true` opens it on any focus, including focus from Tab.
4. Why did it write a date when this field asks for no default? `initDatetimepicker()` maps `data-default-now="false"` to "do not set `defaultDate`" but leaves the library's `useCurrent` at its default (`true`).
5. Why was this not caught? No automated test submits the checkout form by keyboard while leaving the optional date empty. Mouse users who never click the field are not affected.

**Fishbone (cause categories)**

| Category | Contributing cause |
| --- | --- |
| Method | Optional fields are "skipped" by tabbing through them, which focuses them |
| Machine / library | eonasdan-bootstrap-datetimepicker 4.17.49 defaults to `useCurrent: true` |
| Code | One option (`defaultDate`) honours `default_now`; `useCurrent` does not |
| Measurement | No keyboard-path or postcondition test for an empty optional date before this project |
| People | The behaviour is invisible: the value appears only after focus, so reviewers see an empty field |
| Environment | Only on screens with `default_now=false` pickers (checkout due date, custom fields) |

**Corrective action:** set `useCurrent` from `data-default-now`. **Preventive action:** keep DEF-R1 as a regression test (remove `test.fail` after the fix) and add a keyboard path for every form with an optional date picker.

## 2. Risk register input (5 × 5, likelihood × impact)

| ID | Risk | L | I | Score | Owner | Mitigation / tests |
| --- | --- | --- | --- | --- | --- | --- |
| PR-01 | A checkout records the wrong or no borrower (CO-01) | 2 | 5 | 10 | Usman (owner to score) | UC-R1-MAIN/ALT2/EXC1; Usman's API EP/BVA |
| PR-02 | The due date is stored wrong or silently (CO-02) | **4** | 3 | **12** | Rafay | UC-R1-MAIN/ALT2, **DEF-R1 (realised)**, Usman UC1 |
| PR-03 | An unavailable laptop is lent again (CO-03 / eligibility) | 2 | 5 | 10 | Nafay (owner to score) | UC-R2-EXC2, UC-R1-EXC1 (unchanged), white-box eligibility tests |
| PR-04 | Asset name truncated or the limit not enforced (CO-04) | 2 | 3 | 6 | Usman / Nafay | Fix `ed3cb64d`; UC-R2-EXC1/EXC1b; API BVA 254/255/256 |
| PR-05 | Role permission bypass: a reviewer changes loans | 1 | 5 | 5 | Rafay | AC-01…AC-10, UC-R1-EXC2; SEC-07 |
| PR-06 | A return leaves a stale assignment, or a repair laptop becomes lendable (CI-01/CI-03) | 2 | 4 | 8 | Rafay | UC-R2-MAIN/ALT1/EXC2; TEST-01 |
| PR-07 | Exploitable XSS through weak CSP or vulnerable shipped JS / PHP dependencies | 2 | 4 | 8 | Rafay | ZAP passive, composer/npm audit, SEC-01/02, D-01…D-04 |
| PR-08 | Session hijack or an unattended session on a shared lab PC | 3 | 4 | 12 | Rafay | C1 review, SEC-03/04 |
| PR-09 | Keyboard or screen-reader users cannot complete or correct loan tasks | 3 | 3 | 9, now **6** after the checkout fix (L 2) | Rafay | UC-R1 keyboard path, axe + Lighthouse before/after, DEF-R2, U-03 |
| PR-10 | A repeated check-in records a duplicate return (CI-04) | 2 | 4 | 8 | Usman / Nafay (owner to score) | Nafay stale-form test, Usman repeat-request API cases |
| PJ-01 | Environment drift: native `php -S` vs the Docker stack; Docker missing on some machines | 3 | 3 | 9 | Rafay (shared) | Both launchers documented; static-file header difference noted (SEC-06) |
| PJ-02 | Three separate browser setups and shared fixture IDs cause conflicts or flaky interference | 3 | 3 | 9 | Rafay | One shared suite (`tests/team/playwright`), one laptop per test, 1 worker, 3× repeat stability run |
| PJ-03 | AI-assisted work that a member cannot explain at the viva | 3 | 5 | 15 | All | AI-use record, each member re-runs and explains their own tests before submission |

## 3. Exit criteria proposed from this area

| ID | Criterion (measurable) | Tied to | Target | Actual (2026-11-25) |
| --- | --- | --- | --- | --- |
| EC-R1 | Browser use-case flows automated and passing in the combined suite; only triaged known defects may fail, as `test.fail` | PR-01/02/06 | 100% of flows; 0 unexpected failures | Rafay: 2/2 use cases, 11 + 2 known-defect tests, 0 unexpected failures (Nafay and Usman to merge into the shared suite) |
| EC-R2 | Access decisions observed as expected | PR-05 (highest impact) | 100% | 11/11 |
| EC-R3 | Lighthouse accessibility ≥ 90 **and** 0 serious/critical axe violations on both key screens | PR-09 | both screens | Checkout 100 / 0 ✔; checkin 93 / 2 rules ✘ (not met) |
| EC-R4 | No High ZAP passive alert, and no shipped High dependency advisory without a mitigation decision | PR-07, PR-08 | 0 | 0 High ZAP alerts; SEC-02/D-02 (Medium) open with a proposed fix |

## 4. Traceability (requirement → Rafay's tests)

| Req | Tests | Notes |
| --- | --- | --- |
| CO-01 eligible student assignment | UC-R1-MAIN, ALT1, ALT2, EXC1, DEF-R2, AC-02 | n/a |
| CO-02 supplied due date persisted | UC-R1-MAIN, ALT2, DEF-R1 | DEF-R1 open |
| CO-03 unavailable asset rejected, record unchanged | UC-R1-EXC1, UC-R1-EXC2, UC-R2-EXC2, AC-07 | n/a |
| CO-04 255-character name limit | UC-R2-EXC1, UC-R2-EXC1b | Boundary values 254/255/256 are owned by Usman's API suite |
| CI-01 assignee and due date cleared | UC-R2-MAIN, ALT1, ALT2, EXC1, AC-03; EXC1b (rejected, so not cleared) | n/a |
| CI-02 deployable return available again | not in Rafay's cases | Covered by Nafay `return-main` (see TEST-01) |
| CI-03 repair status kept, no checkout | UC-R2-MAIN, ALT1, EXC2 | n/a |
| CI-04 no second return | not in Rafay's cases | Nafay `stale form`, Usman repeat requests |
| Rule: checkout eligibility | UC-R2-EXC2, UC-R1-EXC1 | n/a |
| Rule: role permissions | AC-01…AC-11, UC-R1-EXC2 | n/a |
| Rule: state transitions on return | UC-R2-MAIN, ALT1, EXC2 | deployed → undeployable, deployed → pending, undeployable → checkout refused |
| Rule: 255-character name | UC-R2-EXC1, EXC1b | n/a |
| Usability: task + confirmation | UC-R1-MAIN, UC-R2-MAIN | n/a |
| Usability: error explains the fix, correction succeeds | UC-R1-EXC1 | n/a |
| Usability: keyboard focus order + keyboard submit | UC-R1-MAIN | n/a |

## 5. Coordination notes for the team

* **Nafay (CI):** `bash tests/team/playwright/run-ci.sh <admin-id>` is the one-command browser gate (exit 0/1, JUnit at `output/playwright/junit.xml`). Do not upload `output/playwright/fixtures.json` or `.auth/`. Your specs in `tests/team/browser/` can move to `tests/team/playwright/nafay/` and use the shared fixtures, which avoids a third Playwright install. Please strengthen CI-02 with `user_can_checkout` (TEST-01).
* **Usman:** `tests/team/usman/browser/support.cjs` was written as a stand-in for this shared setup. `signIn`, `choose` and `submit` map to `support/fixtures.cjs` (`technician` fixture, `choose`, a button click). The name boundary: your API suite owns 254/255/256. The browser side shows that the form caps at 255 and the server rejects 256 with the loan intact (UC-R2-EXC1/1b).
* **Duplicate executions:** the reviewer checkout denial runs in both UC-R1-EXC2 and AC-07. UC-R1-EXC2 is the use-case flow (UI path); AC-07 is the access-matrix row. Count it once for the access-control rubric item (AC-07) and once as a use-case flow, or drop one if the team prefers.
