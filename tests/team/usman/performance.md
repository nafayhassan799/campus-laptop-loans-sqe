# Performance: lab technician opens the checkout form (k6)

Script `perf/checkout_form.js`, orchestrator `perf/run_perf.py`, limits `perf/limits.json` (written and committed before any measured run). Raw output: `evidence/perf/` (per-run summary JSON, gzipped raw k6 metrics, stderr, `environment.json`, `comparison.md`).

## Operation and why it was chosen
`GET /hardware/{id}/checkout` as the technician is the first screen of every loan (workflow "Checkout": the technician opens Checkout, selects a student). It is a read of one asset and the form lookups, so it can be repeated thousands of times without changing data. The script logs in with the synthetic technician (CSRF token from the login page, then `POST /login`), keeps the session for the whole run, and counts a request as successful only if the response is HTTP 200, the final URL is not the login page, and the body contains the form posting to `/hardware/{id}/checkout` with the `assigned_user` field. Anything else, including a redirect to login or to the asset list, is an **unexpected failure**.

## Agreed limits (set beforehand)
| Setup | p95 limit | Unexpected-failure limit |
| --- | ---: | ---: |
| 1 simulated user | 1000 ms | 0 |
| 5 simultaneous users | 1500 ms | 0 |

Each run holds the target load for 60 seconds (plus a 5-second ramp for five users), with 1 second of think time between page loads. Two runs per setup, in the order 1, 5, 1, 5, on the same build, machine and starting data.

## Environment
Linux container, 2 CPUs, PHP 8.3.6 built-in server with 4 workers (Laravel's dev router), MariaDB 10.11.14 on the same machine, Snipe-IT v8.8.4 at the pinned commit plus the asset-name fix branch, k6 v0.55.0, synthetic data only (`PERF-001`, deployable and unassigned, reset by `prepare_fixtures.py`). This is not the Docker stack and not a production web server, so absolute times are indicative only.

## Results
| Run | Users | p95 (ms) | p95 limit (ms) | Requests/s | Page loads | Unexpected failures | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1user-run1 | 1 | 158.7 | 1000 | 0.88 | 54 | 0 | PASS |
| 5user-run1 | 5 | 137.0 | 1500 | 4.28 | 280 | 0 | PASS |
| 1user-run2 | 1 | 125.1 | 1000 | 0.89 | 55 | 0 | PASS |
| 5user-run2 | 5 | 131.4 | 1500 | 4.28 | 283 | 0 | PASS |

All four runs are inside both limits. Five users did not slow the form: p95 stayed around 130 to 160 ms and throughput scaled with the number of users (about 0.9 to 4.3 page loads per second, bounded by the 1-second think time).

## Honest notes
* The limits were chosen before measuring and turned out loose: the measured p95 is 8 to 16 percent of the limit, so these runs would not detect a moderate slowdown. Tighten them (for example p95 below 400 ms) when the team agrees a target.
* The one-second think time keeps the request rate low by design; this is a load model of technicians at a desk, not a stress test.
* A first attempt of the final pipeline reported every request as an unexpected failure because `PERF-001` had been left checked out by an earlier manual inspection, which makes the checkout form redirect to the list. The failure check did its job (a redirect is not a success); `prepare_fixtures.py` now always resets the performance laptop first.
* Fixed during development: k6 clears cookies between iterations by default, which logged the user out after one page; the script sets `noCookiesReset: true`.
