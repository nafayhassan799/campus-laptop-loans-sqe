# Findings, defect triage and root-cause notes (API, browser, recovery)

All findings were reproduced on the pinned build (Snipe-IT v8.8.4, commit `60fe07468534a283a473dbfe88244896b44c81bc`) on a local synthetic instance. Evidence files are in `evidence/`.
Severity scale: Critical, Major, Minor, Trivial. Priority: P1 (fix before release) to P5 (note only). The group decides the final classification at triage; the values below are this member's proposal.
No GitHub issue could be filed from the authoring session (no GitHub login), so ready-to-post text is in `issue-drafts.md`.

| ID | Title | Severity | Priority | Status | Test(s) | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| D-API-00 | Asset name silently truncated to 191 characters although the rule allows 255 | Major | P1 | Fixed on `sqe/asset-name-boundary` (commit `ed3cb64d9b`), verified here | `CO.name.length-254-*`, `CO.name.length-255-*` | `evidence/name-truncation-at-191.txt`, `evidence/name-boundary-at-255.txt` |
| D-API-01 | API check-in accepts an invalid `checkin_at` and writes a corrupt history date | Major | P2 | Open | `CI.checkin-at.*` (4 XFAIL) | `evidence/api-results.json` |
| D-API-02 | API check-in applies unvalidated `status_id` / `location_id` with silent type coercion | Major | P2 | Open | `CI.status-id.wrong-type-*`, `CI.location-id.*` (6 XFAIL) | `evidence/api-results.json` |
| D-API-03 | API check-in ignores unrecognised `clear_name` values | Minor | P4 | Open | `CI.clear-name.*` (3 XFAIL) | `evidence/api-results.json` |
| D-API-04 | A JSON number sent as an asset name is coerced to text instead of rejected | Trivial | P5 | Open (observation) | `CO.name.wrong-type-number`, `CI.name.wrong-type-number` | `evidence/api-results.json` |
| D-UI-01 | Due-date picker replaces unparseable text with the current date and time without any message, and the loan is saved with it | Minor | P3 | Open | `UC1-EXC2` | `evidence/browser/` screenshots, `junit.xml` |
| O-API-05 | With the database down, API and web requests answer HTTP 302 to `/setup` (the installer) instead of a 5xx | Minor | P3 | Open (needs team view) | `REC-db-outage` | `evidence/recovery-results.json` |
| O-API-06 | Checkout to an unknown user returns the untranslated message key `validation.exists_undeleted` | Trivial | P5 | Open | probe, `CO.assigned-user.*` | `evidence/api-basis-probes.txt` |

## Details and root causes

### D-API-00 Asset name truncated at 191 (fixed, verified)
Starting point of the project. The model rule is `name => nullable|max:255` (`app/Models/Asset.php`), but the `assets.name` column was `varchar(191)`, so a valid 254 or 255 character name saved without error and was cut.
Verification with the generated cases: with the column temporarily set back to 191 the 254 and 255 cases fail with "name was not persisted in full (191 of 254 chars)" and "(191 of 255 chars)", and the 256 case still rejects and leaves the loan intact. With the 255 column all three behave as the spec says. Root-cause chain (5 Whys, input for the group report): name saved short -> database column narrower than the rule -> the original create migration declares `string('name')` with no explicit length, so `Schema::defaultStringLength(191)` in `app/Providers/AppServiceProvider.php` (line 83) applied, and no later migration widened it -> no test compared rule and schema -> the 255-character limit had no boundary test until CO-04.

### D-API-01 Invalid `checkin_at` stored as a corrupt history date (Major, P2)
`AssetsController::checkin` builds the history date as `$request->input('checkin_at').' '.date('H:i:s')` with no validation. Sent `checkin_at = "not-a-date"`, `"2027-02-29"`, `"2027-13-01"` or `true` the return succeeds (HTTP 200, `status: success`) and the history row is dated `-0001-11-30 00:00:00`. A valid date such as `2028-02-29` is stored correctly. The return record, which the group relies on for "one return recorded", therefore carries a meaningless date. Root cause: the endpoint has no FormRequest (unlike checkout). The browser check-in controller was not checked for the same gap. Suggested fix: validate `checkin_at` as `nullable|date`.

### D-API-02 Unvalidated `status_id` and `location_id` are coerced (Major, P2)
Observed on a loaned laptop, then checked in: `status_id: 1.5` stores status 2, `status_id: true` stores status 1, `location_id: 1.5` stores location 2, `location_id: true` stores location 1, and `location_id: 0` or `"abc"` is accepted and leaves the location empty. All respond HTTP 200 success. A return can therefore land the laptop on a wrong status (possibly a deployable one) or on a wrong location without any error. Nonexistent or non-numeric `status_id` values such as `2147483647` and `"abc"` are refused ("Asset was not checked in"), apparently by the database rather than by validation; this was not traced further. Suggested fix: validate with `integer|exists:status_labels,id` and `integer|exists:locations,id`.

### D-API-03 and D-API-04 (leniency, no data damage)
`clear_name` only acts when it equals `"1"`; any other value is ignored and the return proceeds. A number sent for `name` is stored as its digits. Both are accepted deviations from the typed contract and are listed so the group can decide whether strict typing is wanted.

### D-UI-01 Due-date picker substitutes now() for bad input (Minor, P3)
On the checkout form, typing `not a date`, `2026-13-45` or `2027-02-29` into the Expected Checkin field and leaving it makes the picker overwrite the text with the current date and time (for example `2026-11-22 16:35:28`). No validation message is shown, the checkout succeeds, and the saved `expected_checkin` is that timestamp, so the loan is due immediately. Valid input is accepted: `YYYY-MM-DD` (stored as midnight), and `YYYY-MM-DD HH:MM` or `HH:MM:SS`. Note for test authors: Playwright's `fill()` without focusing the field first also triggers the substitution for valid text; the specs type with keystrokes, as a person does.

### O-API-05 Database outage answered with a redirect to the installer
With the database process stopped, the checkout request returned HTTP 302 to `http://localhost:8000/setup` instead of a 5xx error. Nothing was written and recovery was clean, but an API client or user is pointed at the installer during an outage. Only the redirect was observed; the installer was not followed or used.

### O-API-06 Untranslated validation message
`POST .../checkout` with an unknown `assigned_user` returns `{"assigned_user":["validation.exists_undeleted"]}`: the language key is missing from the English file, so integrators see a raw key.

## Passed behaviors worth noting
* A rejected checkout (non-deployable, archived, deleted asset, unknown user, bad field values, name 256) left the asset and all history rows exactly as before in every case.
* A failed history write rolled the whole checkout back (see `recovery.md`); no partial assignment, status change, counter change or history row remained.
* Two simultaneous checkouts produced one loan and one history row (`S-CONC-01`).
* A repeated empty check-in is rejected; a repeated check-in carrying metadata updates the record without a second return (`S-CI-04a`, `S-CI-04b`).

## Test-environment notes (not product defects)
* API throttle 120 a minute returns HTTP 429 to the generated suite; raised on the local instance only.
* Flash messages after a redirect are lost if a background request from the previous page is still running. The browser helpers wait for the network to settle before navigating and submitting; without that, about 1 in 4 loads of a redirect lost its message.
* The activity report must be read page by page; the generated-case laptop collected more than 500 history rows and a single page hid the newest ones.
* The Playwright browser download is blocked in the authoring sandbox; an installed Chrome was used through `SQE_CHROME_PATH`.
