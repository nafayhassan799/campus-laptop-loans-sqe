# API test basis: contract verified against the pinned build

Owner: Muhammad Usman (24I-3031). Snipe-IT v8.8.4, upstream commit `60fe07468534a283a473dbfe88244896b44c81bc`, local synthetic MariaDB 10.11 database.
Contract file: `tests/team/hardware-loans.openapi.json` (valid OpenAPI 3.0.3, checked with `openapi-spec-validator`).

## How the contract was verified

1. Read the rule sources: `routes/api.php`, `app/Http/Controllers/Api/AssetsController.php` (`checkout`, `checkin`), `app/Http/Requests/AssetCheckoutRequest.php`, `app/Http/Requests/Traits/InfersCheckoutToType.php`, `app/Models/Asset.php` (`availableForCheckout`, `checkOut`, `$rules`), `app/Policies/CheckoutablePermissionsPolicy.php`, and the browser controllers `app/Http/Controllers/Assets/AssetCheckoutController.php` and `AssetCheckinController.php`.
2. Ran the team's unchanged smoke test against the running app (`run_smoke_native.py`; all 4 groups passed, output in `evidence/smoke-test.txt`) and compared its payloads with the spec.
3. Probed the live API with the technician token for every rejection class and recorded the real HTTP code and body.
4. Generated 100 cases from the spec and ran them, plus 16 hand-written scenarios, with a fresh read of the asset and its activity history after every operation.

## Observed behavior, per operation

| Topic | Checkout `POST /hardware/{id}/checkout` | Check-in `POST /hardware/{id}/checkin` |
| --- | --- | --- |
| Validation layer | `AssetCheckoutRequest` (a FormRequest) plus model rules on save | **No request validation.** Only `Asset::save()` rules apply |
| Success | HTTP 200, `status: success`, message "Asset checked out successfully." | HTTP 200, `status: success`, "Asset checked in successfully." |
| Field validation failure | **HTTP 200**, `status: error`, `messages` is a field → messages map | Not rejected for most fields (see findings D-API-01 to D-API-04) |
| Unavailable asset (assigned, deleted, non-deployable or archived status) | HTTP 200, `status: error`, "That asset is not available for checkout!" | n/a |
| Nonexistent asset id | HTTP 200, `status: error`, "Asset not found" | same |
| Already checked in, empty body | n/a | HTTP 200, `status: error` ("already checked in") |
| Already checked in, body with `name`/`status_id`/`location_id`/`clear_name` | n/a | HTTP 200, `status: success`, applied as metadata update; **no second return recorded** (verified: counter and history unchanged) |
| No permission (read-only reviewer) | HTTP 403, nothing changed | HTTP 403, nothing changed |
| Missing or bad token | HTTP 401 | HTTP 401 |
| Concurrent duplicate | One request wins, the other gets `status: error`; one history row, counter +1 | n/a |
| Side effects of a success | `assigned_to`, `expected_checkin`, status label becomes the deployed meta status, `checkout_counter` +1, one `checkout` history row | `assigned_to` and `expected_checkin` cleared, `checkin_counter` +1, one `checkin from` history row, optional status/location/name |

Key decision: because the application answers rejections with HTTP 200, every test asserts the body `status` and then proves the rejection by reading the asset and its history again and comparing every loan field and every history row id with the values captured before the request.

## Gaps between the starter spec and the real workflow inputs

| # | Starter spec said | Pinned build actually does | Action taken |
| --- | --- | --- | --- |
| 1 | Checkout returns 404 and 422 for missing asset and bad fields | Both come back as HTTP 200 with `status: error` | Responses corrected; error status read from the body |
| 2 | Check-in documents 403 and 404 only | Missing asset is HTTP 200/`error`; unauthenticated is 401 | Responses corrected, 401 added |
| 3 | `expected_checkin` is `format: date` | Server rule is `nullable\|date` (anything PHP parses); the browser form posts `YYYY-MM-DD HH:MM:SS` | Kept as a date (team contract), recorded in `x-server-note`; browser behavior covered in UC1 |
| 4 | Checkout body had four fields | Server also accepts `checkout_at`, `note`, `status_id` (must be a deployable status), `requestable`; the browser form also posts `redirect_option` and requires `status_id` | Fields added with their rules |
| 5 | `checkout_to_type` is required | The request infers it from the single filled `assigned_*` field when omitted (even when `null`) | `x-server-infers` added; the generator expects acceptance when it is omitted or null |
| 6 | Check-in body: `status_id`, `name`, `clear_name` | Also `note`, `location_id`, `checkin_at`, `rtd_location_id`, `update_default_location`, `requestable` (the last three are not used by the workflow) | `note`, `location_id`, `checkin_at` added; out-of-scope fields left out |
| 7 | `status_id` on check-in: integer, minimum 1 | No server validation at all; floats and booleans are coerced | Kept as the required contract; the deviations are triaged defects |
| 8 | `name` maxLength 255 | Enforced at model save; the database column was 191 characters (defect fixed on the team branch) | Boundary cases 254/255/256 generated from the spec |
| 9 | Notes optional | Required when the `require_checkinout_notes` setting is on (browser textarea gets `required`; the server also rejects) | Documented; exercised only in the isolated browser fixture |
| 10 | No mention of throttling | Default API limit is 120 requests per minute per token, so a 116-case run is rejected with HTTP 429 | Local instance sets `API_THROTTLE_PER_MINUTE=100000`; recorded as an environment setting |

## Settings that influence the tests

| Setting | Value used | Why |
| --- | --- | --- |
| `API_THROTTLE_PER_MINUTE` | 100000 (local `.env` only) | Generated suite makes several hundred calls a minute |
| `require_checkinout_notes` | off by default; switched on only inside UC2-EXC1 and restored in `finally` | Global setting, so it must never stay on for teammates |
| Timezone | server UTC; browser pickers use the browser's local time | The picker's "now" can differ from the server's date by the machine's offset |
