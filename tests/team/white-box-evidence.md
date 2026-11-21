# Campus Laptop Loans white-box evidence

The test basis is the single-asset Hardware checkout and check-in flow on Snipe-IT v8.8.4. Upstream commit is `60fe07468534a283a473dbfe88244896b44c81bc`. All cases use synthetic assets and users. The PHP suite runs on disposable SQLite. The separate API smoke test verifies actual persisted behavior on the local MariaDB stack, including the asset-name column migration.

## Checkout decision and control-flow graph

The critical decision is `Asset::availableForCheckout()`. A is unassigned, B is undeleted, C is status present, D is status non-archived, and E is deployable. Start leads to A. Each true edge continues to the next condition. Every false edge leads to Reject. E's true edge leads to Allow. Both results lead to Exit.

~~~mermaid
flowchart LR
    Start --> A{A}
    A -->|Yes| B{B}
    B -->|Yes| C{C}
    C -->|Yes| D{D}
    D -->|Yes| E{E}
    E -->|Yes| Allow
    A -->|No| Reject
    B -->|No| Reject
    C -->|No| Reject
    D -->|No| Reject
    E -->|No| Reject
    Allow --> Exit
    Reject --> Exit
~~~

There are 9 nodes, 13 edges, and one connected component. McCabe complexity is **13 − 9 + 2 = 6**. The graph models the short-circuit conditions individually.

## Multiple-condition coverage

Each row is a nominal condition combination. A missing status makes D and E undefined at runtime. For each A/B pair, the executable test uses one missing-status fixture and records the other three rows as masked duplicates. The conflicting archived/deployable flags are possible in an in-memory model fixture and let the test isolate the archived check. Configured status labels normally keep those flags mutually exclusive. The suite exercises **20 distinguishable fixtures**.

| Row | A | B | C | D | E | Expected | Fixture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | 0 | 0 | 0 | 0 | 0 | Reject | No status. D and E are unevaluated. |
| 02 | 0 | 0 | 0 | 0 | 1 | Reject | Masked duplicate of the missing-status fixture. |
| 03 | 0 | 0 | 0 | 1 | 0 | Reject | Masked duplicate of the missing-status fixture. |
| 04 | 0 | 0 | 0 | 1 | 1 | Reject | Masked duplicate of the missing-status fixture. |
| 05 | 0 | 0 | 1 | 0 | 0 | Reject | Ordinary state. |
| 06 | 0 | 0 | 1 | 0 | 1 | Reject | Conflicting flags in an in-memory fixture. |
| 07 | 0 | 0 | 1 | 1 | 0 | Reject | Ordinary state. |
| 08 | 0 | 0 | 1 | 1 | 1 | Reject | Ordinary state. |
| 09 | 0 | 1 | 0 | 0 | 0 | Reject | No status. D and E are unevaluated. |
| 10 | 0 | 1 | 0 | 0 | 1 | Reject | Masked duplicate of the missing-status fixture. |
| 11 | 0 | 1 | 0 | 1 | 0 | Reject | Masked duplicate of the missing-status fixture. |
| 12 | 0 | 1 | 0 | 1 | 1 | Reject | Masked duplicate of the missing-status fixture. |
| 13 | 0 | 1 | 1 | 0 | 0 | Reject | Ordinary state. |
| 14 | 0 | 1 | 1 | 0 | 1 | Reject | Conflicting flags in an in-memory fixture. |
| 15 | 0 | 1 | 1 | 1 | 0 | Reject | Ordinary state. |
| 16 | 0 | 1 | 1 | 1 | 1 | Reject | Ordinary state. |
| 17 | 1 | 0 | 0 | 0 | 0 | Reject | No status. D and E are unevaluated. |
| 18 | 1 | 0 | 0 | 0 | 1 | Reject | Masked duplicate of the missing-status fixture. |
| 19 | 1 | 0 | 0 | 1 | 0 | Reject | Masked duplicate of the missing-status fixture. |
| 20 | 1 | 0 | 0 | 1 | 1 | Reject | Masked duplicate of the missing-status fixture. |
| 21 | 1 | 0 | 1 | 0 | 0 | Reject | Ordinary state. |
| 22 | 1 | 0 | 1 | 0 | 1 | Reject | Conflicting flags in an in-memory fixture. |
| 23 | 1 | 0 | 1 | 1 | 0 | Reject | Ordinary state. |
| 24 | 1 | 0 | 1 | 1 | 1 | Reject | Ordinary state. |
| 25 | 1 | 1 | 0 | 0 | 0 | Reject | No status. D and E are unevaluated. |
| 26 | 1 | 1 | 0 | 0 | 1 | Reject | Masked duplicate of the missing-status fixture. |
| 27 | 1 | 1 | 0 | 1 | 0 | Reject | Masked duplicate of the missing-status fixture. |
| 28 | 1 | 1 | 0 | 1 | 1 | Reject | Masked duplicate of the missing-status fixture. |
| 29 | 1 | 1 | 1 | 0 | 0 | Reject | Ordinary state. |
| 30 | 1 | 1 | 1 | 0 | 1 | Reject | Conflicting flags in an in-memory fixture. |
| 31 | 1 | 1 | 1 | 1 | 0 | Reject | Ordinary state. |
| 32 | 1 | 1 | 1 | 1 | 1 | Allow | Ordinary state. |

### MC/DC pairs

| Condition | Reject / allow rows | What independently changes |
| --- | --- | --- |
| A | 16 / 32 | The current borrower is present versus absent. |
| B | 24 / 32 | The same otherwise eligible asset is deleted versus live. |
| C | 25 / 32 | Status is missing versus present. D and E are masked in row 25 because there is no status object. A unique-cause pair holding D and E observable is infeasible. |
| D | 30 / 32 | The status is archived versus non-archived with deployable held true. |
| E | 31 / 32 | A non-archived status is non-deployable versus deployable. |

## State and persistence assertions

| Requirement | PHP evidence |
| --- | --- |
| CO-01, CO-02 | An eligible request saves the selected borrower and supplied due date. |
| CO-03 | A second checkout keeps the original borrower and due date and adds no second checkout history entry. |
| CO-04 | Names of 254 and 255 characters are saved in full. A 256-character name is rejected with the original state intact. |
| CI-01, CI-02 | Returning a laptop clears the borrower, type, and due date. A deployable return can be lent again. |
| CI-03 | Returning into repair clears the loan while a subsequent checkout is rejected. |
| CI-04 | Repeated check-in requests add no second return event. A request with metadata can still update those fields. |
| Role permissions | A reviewer can read the asset and cannot perform the checkout or check-in. Both records stay intact after the denied operations. |

Both browser workflows have a normal path, two alternatives, and two exceptions. The browser suite checks the UI outcome and reads saved state through the REST API. The browser seed uses fresh synthetic records for each run. The existing API smoke test remains the MariaDB regression for [the asset-name fix](https://github.com/nafayhassan799/campus-laptop-loans-sqe/pull/1).
