# GitHub issue drafts

The authoring session had no GitHub login, so these were not filed. Post each with `gh issue create --title ... --body-file ...` (or paste into the web form) and add the labels shown. Replace "see evidence" with the file links once the evidence is pushed.

---
## D-API-01: API check-in accepts an invalid `checkin_at` and writes a corrupt history date
Labels: `bug`, `api`, `sqe-major`, `priority-P2`

**Steps** (local synthetic instance, technician token, laptop checked out to a student):
1. `POST /api/v1/hardware/{id}/checkin` with `{"checkin_at": "2027-02-29"}` (or `"not-a-date"`, `"2027-13-01"`, `true`).
2. `GET /api/v1/reports/activity?item_type=asset&item_id={id}`.

**Expected** HTTP 200 with `status: error` (validation) and the loan left intact, like checkout.
**Actual** HTTP 200 `status: success`; the loan is cleared and the new `checkin from` history row is dated `-0001-11-30 00:00:00`. A valid `2028-02-29` is stored correctly.
**Cause** `AssetsController::checkin` concatenates `checkin_at` with the time of day and never validates it.
**Suggested fix** validate `checkin_at` as `nullable|date` before the transaction.
**Evidence** generated cases `CI.checkin-at.*` in `evidence/api-results.json`.

---
## D-API-02: API check-in applies unvalidated `status_id` and `location_id` with silent type coercion
Labels: `bug`, `api`, `sqe-major`, `priority-P2`

**Steps** check out a laptop, then `POST /api/v1/hardware/{id}/checkin` with `{"status_id": 1.5}`, `{"status_id": true}`, `{"location_id": 1.5}`, `{"location_id": true}`, `{"location_id": 0}` or `{"location_id": "abc"}`.
**Expected** a validation error and an unchanged loan.
**Actual** HTTP 200 success every time. `status_id: 1.5` stores status 2, `true` stores status 1; `location_id: 1.5` stores location 2, `true` stores location 1; `0` and `"abc"` are accepted and leave the location empty.
**Suggested fix** validate `status_id` as `nullable|integer|exists:status_labels,id` and `location_id` as `nullable|integer|exists:locations,id`.
**Evidence** `CI.status-id.wrong-type-*`, `CI.location-id.*`.

---
## D-UI-01: Expected Checkin picker silently replaces invalid text with the current date and time
Labels: `bug`, `ui`, `sqe-minor`, `priority-P3`

**Steps** open `/hardware/{id}/checkout`, choose a student, type `not a date` (or `2026-13-45`, `2027-02-29`) in Expected Checkin, click elsewhere, submit.
**Expected** a validation message, or an empty field.
**Actual** the field is overwritten with the current date-time, no message appears, "Asset checked out successfully", and the saved expected return date is that timestamp (the loan is due immediately).
**Evidence** Playwright test `UC1-EXC2` with screenshot.

---
## O-API-05: Database outage answered with a redirect to /setup
Labels: `observation`, `recovery`, `sqe-minor`, `priority-P3`

With the database stopped, `POST /api/v1/hardware/{id}/checkout` returned HTTP 302 with `Location: http://localhost:8000/setup`. Expected a 5xx error response. No data was written and recovery after restart was clean. Only the redirect was observed. Evidence: `evidence/recovery-results.json` (mode `db-outage`).

---
## D-API-03 / D-API-04 / O-API-06 (low priority, can be batched)
* Check-in ignores unrecognised `clear_name` values (any value other than `"1"`): HTTP 200 success.
* A JSON number sent as `name` is stored as text on checkout and check-in.
* Checkout to an unknown user returns the raw key `validation.exists_undeleted` instead of text.
