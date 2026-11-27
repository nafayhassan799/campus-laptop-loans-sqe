# Controlled recovery test

Script: `recovery/recover_checkout.py`. Raw output: `evidence/recovery-results.json`, `evidence/recovery-log.txt`. Each fault uses its own laptop (`RECOV-001`, `RECOV-002`) in the disposable local database.

## Method

Checkout writes in this order inside one database transaction (`AssetsController::checkout`): lock and re-check the asset, `UPDATE assets` (assignee, due date, status, location), then the synchronous `CheckoutableCheckedOut` listener inserts the `checkout` row into `action_logs`. A failure of the second write after the first is the case that could leave a partial assignment.

| Fault | How it is injected | Failure point | What must be true afterwards |
| --- | --- | --- | --- |
| `history-write` | `BEFORE INSERT` trigger on `action_logs` that signals an error for the `checkout` row of the fixture laptop | **After** the asset row was updated, **before** the history row is stored | The transaction rolls back: no assignee, status unchanged, counter unchanged, `last_checkout` unchanged, no history row |
| `db-outage` | The database process is stopped before the request | Before any write | After restart the record is unchanged |

Steps for each fault: capture the before state through the API and straight from the database; inject; send the checkout and require that it does **not** report success; read back (API and SQL) and compare; restore the dependency (drop the trigger, or start the database and wait until it answers); confirm the record is still unchanged; **retry the identical request** and require success; assert exactly one assignment, status deployed, due date stored, `checkout_counter` +1 and exactly one new `checkout` history row; send the same request a third time and require rejection with no new history row or counter change. Cleanup always removes the trigger or restarts the database and resets the laptop.

## Result (final run)

| Fault | Failed attempt | Record during/after fault | Retry | Duplicate check |
| --- | --- | --- | --- | --- |
| `history-write` | HTTP 500 `Server Error` | Unchanged: assignee empty, status, counter, `last_checkout` and history rows identical | HTTP 200 `success`: one assignment, counter +1, one history row | Third request rejected, nothing added |
| `db-outage` | HTTP 302 to `/setup` (see finding O-API-05) | Unchanged after restart | HTTP 200 `success`: one assignment, counter +1, one history row | Third request rejected, nothing added |

Conclusion: the checkout write is atomic under a history-store failure and safe to retry; a retry cannot create a second loan or a second history entry. Limit: the trigger models a failing local dependency on the history table, not every possible failure (for example a crash of the PHP process after commit but before the response, which would need a client retry rule of its own).
