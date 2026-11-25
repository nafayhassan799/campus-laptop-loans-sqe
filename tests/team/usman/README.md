# Muhammad Usman: API, test data, performance and recovery

Section A, 24I-3031. Everything here sits under `tests/team/usman/`, plus the contract at `tests/team/hardware-loans.openapi.json`.
Upstream Snipe-IT tests are not part of this work.

| Folder or file | What it is |
| --- | --- |
| `../hardware-loans.openapi.json` | Validated OpenAPI 3.0.3 contract for checkout, check-in and the read-back |
| `api-test-basis.md` | Contract verified against the pinned code and running app, with the gap list |
| `api/generate_cases.py` | Test-data generator: reads the spec, emits equivalence partitions and three-point boundaries (no Docker needed) |
| `api/run_api_tests.py` | Executes the generated cases and 16 scenarios with read-back and history checks |
| `api/known-defects.json` | Triaged defects whose test is expected to fail (XFAIL); a fixed defect that still passes is reported as XPASS and fails the run |
| `api/spec_change_demo.py` | Viva example: change two constraints in a copy of the spec and see which cases move |
| `perf/` | k6 script, agreed limits (`limits.json`, committed before the runs) and the four-run orchestrator |
| `recovery/recover_checkout.py` | Controlled failure-and-retry test for the checkout write |
| `browser/` | Two Playwright use cases (10 tests) |
| `prepare_fixtures.py` | Seeds synthetic users, statuses, locations and per-purpose laptops; writes local credentials to `output/usman/fixtures.json` (git-ignored) |
| `run_all.py` | One command and one exit code for CI |
| `start_native.sh` | Docker-free launcher for Linux (MariaDB plus PHP dev server) |
| `traceability.md`, `findings.md`, `issue-drafts.md`, `performance.md`, `recovery.md`, `hours-and-ai-use.md` | Handover documents |
| `evidence/` | Raw results from the final run |

## Run it

With the team's Docker stack (PowerShell 7, Docker Compose, Python 3, Node 22; from the repository root):

```powershell
pwsh -NoProfile -File tests/team/start-local.ps1
python -B tests/team/usman/run_all.py --admin-id 1                 # contract, generator, fixtures, API, recovery, browser
python -B tests/team/usman/run_all.py --admin-id 1 --stages perf  # four k6 runs, about 5 minutes (needs k6 on PATH)
```

Complete Snipe-IT's first-run setup at <http://localhost:8000> with a synthetic admin first and use that admin's numeric id.
`k6` and Playwright's browser are installed separately (`winget install k6`, `cd tests/team/usman/browser; npm install; npx playwright install chromium`).

Without Docker (Linux; this is how the committed evidence was produced):

```bash
bash tests/team/usman/start_native.sh                  # MariaDB + PHP workers on :8000; needs composer install done once
python3 -B <initialize script>                          # create the synthetic admin once (tests/team/initialize_local.py on Nafay's branch)
export SQE_ARTISAN="php artisan" SQE_DB_CMD="mariadb -uroot snipeit"
export SQE_DB_STOP_CMD="mysqladmin -uroot shutdown"
export SQE_DB_START_CMD="bash -c 'nohup mysqld_safe --user=mysql >/tmp/sqe-mysqld.log 2>&1 &'"
export SQE_CHROME_PATH=/usr/bin/google-chrome           # only if Playwright cannot download its own browser
python3 -B tests/team/usman/run_all.py --admin-id 1 --stages contract,generate,fixtures,api,recovery,browser,perf
```

Single pieces: `python -B tests/team/usman/api/generate_cases.py --out out.json`, `python -B tests/team/usman/api/run_api_tests.py --admin-id 1 [--only CO.name] [--spec other.json]`, `python -B tests/team/usman/recovery/recover_checkout.py --admin-id 1 --mode history-write`, `cd tests/team/usman/browser && npx playwright test`.

## Exit codes (for Nafay's CI)

| Command | 0 | 1 | 2 |
| --- | --- | --- | --- |
| `run_all.py` | every selected stage passed | a stage failed | a prerequisite is missing |
| `run_api_tests.py` | all pass or XFAIL | any unexpected FAIL or any XPASS | setup error |
| `recover_checkout.py` | both faults recovered | an assertion failed | n/a |
| `run_perf.py` | all four runs inside the limits | a p95 or failure limit was exceeded | k6 or fixtures missing |
| `npx playwright test` | 10 passed | a test failed | n/a |

JUnit output: `output/usman/api/junit.xml`, `output/usman/browser/junit.xml`. Stage logs: `output/usman/logs/`.
Suggested workflow step: run `run_all.py` after the stack is up and upload `output/usman/` (excluding `fixtures.json`) as the artifact.

## Environment rules that matter

* Use only a local synthetic instance. `fixtures.json` holds temporary tokens and generated passwords; it lives under the git-ignored `output/` and must never be committed.
* `API_THROTTLE_PER_MINUTE` must be raised for the local instance (default 120 a minute rejects the generated suite with HTTP 429).
* Each purpose owns its own laptop (`API-GEN-001`, `API-FLOW-001`, `PERF-001`, `RECOV-001/2`, `BR-CO-xx`, `BR-CI-xx`), so Nafay's `LAB-001` tests and mine do not collide. Playwright runs with one worker because UC2-EXC1 switches the global "check-in notes required" setting on and restores it in a `finally` block; do not run it in parallel with another browser suite.
* Reset: every test resets its own laptop first. To wipe everything, recreate the database and re-run `prepare_fixtures.py`.

## Dependencies on the other two members

* Rafay's shared Playwright fixtures were not on any branch when this was written, so `browser/support.cjs` contains small local equivalents (sign-in, select2 helper, API read-back). Replace them with the shared ones when they land; the specs only use `signIn`, `choose` and `submit`.
* Nafay owns CI: `run_all.py` is the hand-off. The existing workflow on `sqe/nafay-quality` does not call it yet.
* Risk IDs `R-A1` to `R-A8` (defined in `traceability.md`) are this member's working labels; renumber them to the team's risk register when it exists.
