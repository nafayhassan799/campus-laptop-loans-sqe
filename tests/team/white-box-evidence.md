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

SonarQube Community Build 26.11.0 reported **6** for `availableForCheckout()`. A separate local PHP profile activated rule `php:S1541` with a diagnostic threshold of 5 to expose the per-function value. This profile was used for the measurement only. The project scan uses its normal PHP quality profile.

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

## Browser and MariaDB evidence

Playwright passed all ten Chromium scenarios. Each browser run seeds fresh synthetic assets.

| Use case | Main flow | Alternative flows | Exception flows |
| --- | --- | --- | --- |
| Check out a laptop | Check out a deployable laptop to Sara and verify the saved borrower and status. | Lend to Ali. Select a different deployable status. | An assigned laptop and an undeployable laptop each redirect to Hardware without rendering the checkout form or changing the borrower, status, or counter. |
| Return a laptop | Check in a loaned laptop and verify that it can be lent again and that its borrower and due date are cleared. | Return under another deployable status. Include a note and confirm it in the history. | A stale form adds no second return. A read-only reviewer sees no check-in control and a direct visit returns 403 without changing the loan. |

### Asset-name defect and regression

The checkout API accepted a name within its 255-character limit, but a fresh read returned a shorter name. MariaDB showed that the `assets.name` column was `varchar(191)`. This can silently lose part of a laptop's name during a normal loan. The migration aligns the column with the existing validation limit. [Asset-name fix and regression](https://github.com/nafayhassan799/campus-laptop-loans-sqe/pull/1)

The comparison used the same smoke test and API contract on two independently initialized MariaDB databases with synthetic fixtures.

| Revision | Column type | Observed result |
| --- | --- | --- |
| `cc92ea0776` before the fix | `varchar(191)` | Exit 1. The API accepted the 254-character name, but the read-back assertion failed. The suite stopped at that case. |
| `ed3cb64d9b` after the fix | `varchar(255)` | Exit 0. Names of 254 and 255 characters persisted in full. A 256-character name was rejected and the loan stayed unchanged. Loan lifecycle and role checks also passed. |

The local transcripts and comparison are in `output/nafay-quality/asset-name-proof/`.

## PHPUnit coverage

PHPUnit 11.5.55 with PHP 8.5.4 and Xdebug 3.5.0 passed 32 tests and 126 assertions. The table reports executable lines and branches observed by Xdebug.

| Method | Executable lines | Branches |
| --- | ---: | ---: |
| `Asset::availableForCheckout()` | 6/6 | 11/11 |
| `Asset::checkOut()` | 25/28 | 25/29 |
| `AssetCheckoutRequest::rulesArray()` | 20/20 | 3/3 |
| REST `AssetsController::checkout()` | 34/48 | 23/37 |
| REST `AssetsController::checkin()` | 74/85 | 6/7 |
| `CheckoutablePermissionsPolicy::checkout()` | 1/1 | 1/1 |
| `CheckoutablePermissionsPolicy::checkin()` | 1/1 | 1/1 |

The uncovered model lines handle checkout to the asset itself, checkout to a location, and lookup by numeric administrator ID. These are outside the ordinary technician-to-student workflow. The REST controllers also serve other asset flows, such as location and asset assignees, explicit relocation, licenses, and pending acceptance cleanup. Their method totals include those paths and expose gaps even within related flows, such as a deleted student target, a historical return, a concurrent return between the initial check and database lock, and a failed save. The observed repeat-return scenario covers a sequential repeat.

## Mutation evidence

Infection 0.35.12 mutated covered statements in `app/Models/Asset.php` using the isolated SQLite test suite. The initial run had 210 mutants, with 78 killed and 132 surviving, for **37.14% MSI**. The expanded suite covered two additional mutation sites and killed 105 of 212 mutants, for **49.53% MSI**. There were 107 survivors in the final run. Both custom mutants triggered test assertion failures in both runs, with zero tool errors or timeouts.

| Team operator | Domain-specific change | Assertion that detects it |
| --- | --- | --- |
| `AvailabilityUsesPendingFlag` | Reads the pending flag where checkout eligibility should inspect deployability. The built-in boolean mutations do not substitute one domain field for the other. | The availability matrix asserts the decision for eligible and ineligible status combinations. |
| `ReintroduceAssetNameTruncation` | Writes only 191 characters during checkout. It models the observed database truncation at the persistence boundary. | The 254- and 255-character cases assert the full stored name after a fresh read. |

The focused rerun retested 24 original survivor IDs. After checking the persisted borrower, dates, event metadata, location, and counter, **22 of 24 were killed**. The rows record the individual changes and their classification.

| Original ID prefix | Change | Classification | Focused rerun |
| --- | --- | --- | --- |
| `137cd988` | Removes an inner `return false` in the availability check. | Equivalent for this code. Execution proceeds to the unconditional `return false`. | Survived |
| `d2cd30e3` | Defaults `signInPlace` to true. | Untested event option. The normal loan scenarios do not inspect the sign-in-place event field. | Survived |
| `81cb2ade` | Inverts the location override condition. | Persisted location. Exercise explicit override and borrower-home fallback. | Killed |
| `29ad1a3a` | Inverts the target-is-a-location check. | Persisted location. A student is never a location target. | Killed |
| `3d472b08` | Inverts the same-day comparison. | Event timestamp. Compare historical and same-day loans. | Killed |
| `0b76fdd4` | Replaces the historical-date conjunction with OR. | Event timestamp. Require the action date flag only on a historical loan. | Killed |
| `2f07fc1b` | Negates both historical-date predicates. | Event timestamp. Same-day and missing dates must omit the flag. | Killed |
| `e2fc978b` | Negates the date guard. | Event timestamp. Historical and same-day cases give different outcomes. | Killed |
| `f74e2848` | Negates the supplied timestamp check. | Event timestamp. Cover both supplied and absent timestamps. | Killed |
| `4407ad6a` | Flips the explicit operator's user-class check. | Event attribution. The explicit operator differs from the authenticated user. | Killed |
| `548f1efd` | Replaces the explicit-operator conjunction with OR. | Event attribution. The omitted operator falls back to the authenticated user. | Killed |
| `2f7e1ec1` | Negates both operator predicates. | Event attribution. Check explicit and default operator cases. | Killed |
| `5d62eb8c` | Negates the complete explicit-operator guard. | Event attribution. Check the exact actor recorded in both cases. | Killed |
| `1945fcb8` | Negates the operator-presence check. | Event attribution. Check that a supplied user wins over the session user. | Killed |
| `65ef9436` | Changes checkout event quantity from 1 to 0. | Event quantity. The event represents one laptop. | Killed |
| `44a6a3e3` | Changes checkout event quantity from 1 to 2. | Event quantity. Assert exactly one laptop. | Killed |
| `05950bed` | Changes the checkout counter increment from 1 to 0. | Persisted counter. Read the saved increment. | Killed |
| `1ef0cea1` | Changes the checkout counter increment from 1 to 2. | Persisted counter. Require a single increment. | Killed |
| `d6a667ad` | Removes the checkout counter update. | Persisted counter. Confirm the counter changed. | Killed |
| `2ac85907` | Inverts the user-assignee comparison. | Assignee type. Confirm the loan is flagged as a user checkout. | Killed |
| `df641b87` | Reduces visibility of `assignedType()`. | Public model contract. The test reads the public method. | Killed |
| `8f8ac21c` | Removes lowercasing of the assignee type. | Assignee type format. Assert the exact string `user`. | Killed |
| `a7ce83cb` | Inverts the assignee-type conditional. | Assignee type. A stored borrower must expose its type. | Killed |
| `bed59feb` | Removes the assignee-type return. | Assignee type. A stored borrower must produce `user`. | Killed |

## SonarQube baseline

The local scan used SonarQube Community Build 26.11.0.134175 and the default Sonar way core PHP profile across `app/`. It imported JUnit and Clover results from the team's scoped suite. The project-wide percentages include the rest of the pre-existing application.

| Measure | Observed | Interpretation |
| --- | ---: | --- |
| Non-comment source lines | 119,317 | Size of the PHP application scope scanned by SonarQube. |
| Cyclomatic / cognitive complexity | 20,899 / 19,748 | Aggregate decision and comprehension costs across the application. The checkout eligibility decision was measured separately at 6. |
| Duplicated lines | 14.1% | Shared behavior can diverge when fixes are made in only one copy, especially across parallel paths. |
| Bugs / code smells / vulnerabilities | 10 / 3 / 22 | Static analyzer classifications across the inherited app. Observations need source review and scoped triage before being treated as verified defects. |
| Security hotspots / blocker issues | 0 / 0 | The configured profile reported neither category in this scan. |
| Technical debt | 90 minutes | The analyzer's remediation effort estimate for its maintainability findings. |
| Reliability / security / maintainability | C / D / A | Baseline ratings with technical debt and issue severity considered separately. |
| Overall coverage / line coverage | 0.9% / 0.9% | The team covers two workflows within a much larger application. Use the Xdebug method report for branch coverage of the loan rules. |
| Built-in gate | OK | The final local scan evaluated zero new-code violations and 0.0% new-code duplication. CI also enforces absolute limits against the pinned baseline. |

The Sonar step checks for zero blockers, reliability C or better, and security D or better on this pinned baseline. The project gate independently requires complete statement and branch coverage of checkout eligibility, checkout validation rules, and the two scoped permission decisions. It also requires both custom mutations to trigger test assertion failures and sets a 49% MSI floor below the improved score of 49.53%.

## GitHub evidence

[Draft PR #2](https://github.com/nafayhassan799/campus-laptop-loans-sqe/pull/2) adds the quality workflow and team tests. The `SQE quality gate` check is required on `main`, including for administrators. The inherited upstream workflows were individually disabled before enabling Actions.

GitHub reported an account billing lock before starting any job, including on the retry against protected `main`. A genuine hosted test pass and a PR blocked by a failing business test are still required. [Initial attempt](https://github.com/nafayhassan799/campus-laptop-loans-sqe/actions/runs/44909961315) · [Retry on PR #2](https://github.com/nafayhassan799/campus-laptop-loans-sqe/actions/runs/44911266729/attempts/2)

Once the workflow is on the protected branch and Actions can start jobs, the team can demonstrate the gate on a temporary non-draft PR to `main` using the 255-character regression. Removing the column-widening migration from the PR should make the MariaDB smoke test expose the original truncation. Save the failing check and GitHub's blocked merge state, restore the migration on the same PR, and record the successful rerun. Keep the expected result and platform availability separate from the observed result.

## Coursework handoff

Add the partial controller coverage and check-in concurrency gap to the shared test report when the group assesses release risk. Use the hosted evidence only after actual jobs run. Record personal time and teammate review in the group log as those activities occur.

| AI tool | Work assisted | Evidence checked in this session |
| --- | --- | --- |
| OpenAI Codex | Rule and test design, PHPUnit and Playwright implementation, mutation and SonarQube runners, CI configuration, and evidence drafting. | Executed PHPUnit, Chromium, API smoke, Infection, and SonarQube against synthetic fixtures. Checked the GitHub branch protection and billing annotations. |

## Reproduction

Run these commands from the repository root with Docker running. Start the local Snipe-IT stack and finish its first-run setup before the API and browser commands.

~~~powershell
New-Item -ItemType Directory -Force output/nafay-quality | Out-Null
$evidence = (Resolve-Path output/nafay-quality).Path
docker build -t sqe-php-quality -f tests/team/Dockerfile.quality .
docker run --rm -e XDEBUG_MODE=coverage -v "${evidence}:/evidence" sqe-php-quality vendor/bin/phpunit -c tests/team/phpunit.xml --path-coverage --coverage-php /evidence/coverage.cov --coverage-clover /evidence/clover.xml --log-junit /evidence/phpunit-junit.xml
docker run --rm -v "${evidence}:/evidence" sqe-php-quality php tests/team/check_coverage.php
docker run --rm -e XDEBUG_MODE=coverage -v "${evidence}:/evidence" sqe-php-quality /opt/sqe-infection/vendor/bin/infection --configuration=tests/team/infection.json5 --only-covering-test-cases --threads=4 --min-msi=49 --logger-summary=/evidence/infection-final-summary.json Asset.php
python -B tests/team/check_mutation.py
python -B tests/team/run_sonar.py --require-gate
npm ci --prefix tests/team/browser
node tests/team/browser/node_modules/@playwright/test/cli.js install chromium
python -B tests/team/smoke_checkout.py --admin-id 1
python -B tests/team/run_browser.py --admin-id 1
~~~

Use the numeric ID of the local synthetic administrator if it differs from 1. The coverage breakdown, scanner measures, mutant reports, and browser report are written under `output/nafay-quality/`.

To reproduce the initial mutation score, build the test image from a separate checkout at `4e4350f487`. Run the same Infection command without the final MSI floor and write the results into a separate evidence directory. The initial, selected, and final local JSON reports contain the complete mutant IDs and individual diffs.
