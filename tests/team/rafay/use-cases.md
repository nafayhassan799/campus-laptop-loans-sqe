# Rafay Imran: browser use cases

Section A, 24I-3026. System under test: Snipe-IT v8.8.4 (upstream commit `60fe0746`) plus the team's asset-name migration (`ed3cb64d`), on a local synthetic MariaDB database.
Specs: `tests/team/playwright/rafay/uc-r1-keyboard-checkout.spec.cjs` and `uc-r2-repair-return.spec.cjs`.
Every flow below was first observed by hand in the running app, then automated. The assertions match the behaviour as observed, not the plan, and the differences are listed at the end.

Actors: **Lab technician** `sqe_lab_technician` (`assets.view`, `assets.checkout`, `assets.checkin`) and **read-only reviewer** `sqe_read_only` (`assets.view`).
Seeded students: Sara SQE (`sqe_student_sara`) and Ali SQE (`sqe_student_ali`). Status labels: *SQE Ready to Deploy* (deployable), *SQE Needs Repair* (undeployable), *SQE Pending Assessment* (pending).
Each test owns one laptop (`RAF-CO-*`, `RAF-CI-*`) and resets it first, so tests never share a record.

## UC-R1 Complete a student checkout using the keyboard

| | |
| --- | --- |
| Goal | Lend one laptop to an eligible student without using a mouse |
| Requirements | CO-01, CO-02, CO-03, usability (task completion, error correction, keyboard), role permissions |
| Precondition | Laptop is unassigned, not deleted, status *SQE Ready to Deploy*; the technician is signed in |
| Success postcondition | The same asset record has `assigned_to` = the chosen student and `expected_checkin` = the typed date. Status meta is *deployed*, `checkout_counter` is +1 and the history has exactly one more `checkout` event. The confirmation "Asset checked out successfully." is shown |
| Failure postcondition | Asset unchanged: assignee, due date, status and `checkout_counter` are the same as before |

**Main flow (UC-R1-MAIN).**
1. The technician opens *Checkout* for the laptop.
2. They press Tab from the top of the page. Focus goes through Asset Name, Status, Requestable, Checkout-to, **User**, Location, Default Location, Checkout Date, Expected Checkin Date, Notes, Cancel, After-saving and **Checkout**, in that order. The test asserts this order.
3. On *User*, Enter opens the picker. They type "Sara" and press Enter to choose *Sara SQE (sqe_student_sara)*.
4. On *Expected Checkin Date*, they replace the field's value with a date 14 days ahead and press Escape.
5. They Tab to *Checkout* and press Enter.
6. The system shows the confirmation and saves the loan. The postcondition is checked by REST read-back and the activity history.

| Flow | What changes | Test |
| --- | --- | --- |
| ALT1 | At step 4+ the technician tabs to *Notes* and types a note. The note is saved on the new `checkout` history event | UC-R1-ALT1 |
| ALT2 | At step 3 they type "sqe_student". Both students are listed (sorted, Ali first). They use the arrow keys to highlight *Ali SQE* and press Enter. Ali is saved with the 3-day due date | UC-R1-ALT2 |
| EXC1 | Business-rule rejection, then correction. At step 2 they tab straight to *Checkout* without choosing a borrower. The form's validator blocks the submit: no POST is sent, the User row gets `has-error` and a `role="alert"` message "This field is required", and the asset is unchanged. They then choose Sara by keyboard, add a due date and submit. Exactly one POST is sent, it succeeds and `checkout_counter` is +1 | UC-R1-EXC1 |
| EXC2 | The reviewer opens the same laptop: no Checkout link. A GET of the checkout form returns 403 with no form. The same form POST, sent with the reviewer's own session and CSRF token, returns 403. The asset is unchanged | UC-R1-EXC2 |

Known open defects. They are not `test.fail()` tests, because those would also accept setup errors and unrelated failures. Each test runs the flow with strict assertions and then asserts the exact defect signature. It passes only while that defect is present, and it fails with "… looks fixed" once the defect is fixed:

| Test | Defect |
| --- | --- |
| DEF-R1 | Tabbing past the empty optional *Expected Checkin Date* saves the current date and time as the due date (CO-02). Expected: no due date. Signature asserted: the field was empty, it holds a browser time between the start and end of the Tab walk, and exactly that value is saved |
| DEF-R2 | When the chosen borrower is deleted before submit, the server correctly rejects the checkout. But the User field error reads `validation.exists_undeleted`, which does not tell the technician what to do. Signature asserted: same form, User row flagged, asset unchanged, and the message contains `validation.exists_undeleted` |

## UC-R2 Return a damaged laptop for repair

| | |
| --- | --- |
| Goal | Take a laptop back from a student and keep it out of circulation until it is repaired |
| Requirements | CI-01, CI-03, CO-03, CO-04 |
| Precondition | Laptop is checked out to Sara with a due date (set through the API by `loanAsset`); the technician is signed in |
| Success postcondition | `assigned_to` and `expected_checkin` are null and the status is the chosen non-deployable label. `user_can_checkout` is false (the API's own eligibility flag), `checkin_counter` is +1 and there is exactly one more `checkin from` event. The confirmation "Asset checked in successfully." is shown. The record page shows the status and no Checkout link |
| Failure postcondition | The loan is intact: same assignee, due date, status and `checkin_counter`, and no new return event |

**Main flow (UC-R2-MAIN).**
1. The technician opens *Checkin* for the laptop and sees the "checked out to Sara SQE" panel.
2. They choose *SQE Needs Repair* as the status.
3. They press *Checkin*.
4. The system shows the confirmation and saves the return. The test checks the postcondition through the REST read-back and also by loading the record page separately.

| Flow | What changes | Test |
| --- | --- | --- |
| ALT1 | At step 2 the technician chooses the separate pending status *SQE Pending Assessment*. Status meta *pending* is kept and the laptop is still not lendable | UC-R2-ALT1 |
| ALT2 | At step 2 they also type a damage note. The note is on the new `checkin from` event and can be found in the asset's History tab with the table's search box | UC-R2-ALT2 |
| EXC1 | Over-limit asset name on the return form. The field has `maxlength=255`: typing 256 characters keeps 255 and shows no message. The return succeeds and the 255-character name is stored in full | UC-R2-EXC1 |
| EXC1b | The same limit on the server, for a client that does not apply `maxlength`. A 256-character name is rejected with "Asset was not checked in, please try again" and "The name field must not be greater than 255 characters.". The loan is unchanged, with no new return event. The user lands on the asset list, so the form input is lost (finding U-03) | UC-R2-EXC1b |
| EXC2 | Lending the laptop after the repair return. The record page shows no Checkout link. Opening the checkout URL directly redirects to the asset list with "That asset is not available for checkout!". `assigned_to`, the repair status and `checkout_counter` are unchanged | UC-R2-EXC2 |

## Where the app differed from the plan (assumptions and findings)

| Plan | Observed on the pinned build | What the tests do |
| --- | --- | --- |
| Over-limit name rejected with a message on the form | The browser's `maxlength=255` silently stops typing at 255, for both checkout and checkin. Only a client without `maxlength` reaches the server rule, which then rejects with a clear message but redirects to the list | EXC1 asserts the cap and the full 255-character save. EXC1b asserts the server rule and the intact loan (coordinate the boundary with Usman's API cases) |
| A rejected checkout is reported by the server | An empty borrower is stopped by jQuery Validate in the browser. Nothing reaches the server | EXC1 asserts that no POST was sent, then checks the alert text and the unchanged asset |
| `available_actions.checkout` = can be lent | It reports only the caller's permission. It is `true` for a laptop in repair | The tests use `user_can_checkout`, which calls `Asset::availableForCheckout()`. Nafay's return tests use `available_actions.checkout` as evidence for CI-02; share this so it can be strengthened |
| Optional due date stays empty when skipped | The date picker fills in the current time when it gets focus | DEF-R1 (known defect) |
