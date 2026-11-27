# Performance: lab technician opens the checkout form (k6)

Script `perf/checkout_form.js`, orchestrator `perf/run_perf.py`, limits `perf/limits.json` (written and committed before any measured run). Raw output: `evidence/perf/` (per-run summary JSON, gzipped raw k6 metrics, stderr, `environment.json`, `comparison.md`).

## Operation and why it was chosen
`GET /hardware/{id}/checkout` as the technician is the first screen of every loan (workflow "Checkout": the technician opens Checkout, selects a student). It is a read of one asset and the form lookups, so it can be repeated thousands of times without changing data. The script logs in with the synthetic technician (CSRF token from the login page, then `POST /login`), keeps the session for the whole run, and counts a request as successful only if the response is HTTP 200, the final URL is not the login page, and the body contains the form posting to `/hardware/{id}/checkout` with the `assigned_user` field. Anything else, including a redirect to login or to the asset list, is an **unexpected failure**.

## Agreed limits (set beforehand)
| Setup | p95 limit | Unexpected-failure limit |
| --- | ---: | ---: |
| 1 simulated user | 1000 ms | 0 |
| 5 simultaneous users | 1500 ms | 0 |

Each run starts 1 or 5 virtual users, allows 5 seconds for sign-in and warm-up, then measures requests started over 60 seconds at that same load. The virtual users wait 1 second between iterations. All four runs use the same runner, build, and fixtures, in the order 1, 5, 1, 5.

## Environment
The [GitHub Actions rerun](https://github.com/nafayhassan799/campus-laptop-loans-sqe/actions/runs/46026037630) used a four-CPU Linux runner, the team's disposable Snipe-IT v8.8.4 Docker stack with MariaDB 13.0.2, and k6 v0.55.0. The synthetic laptop `PERF-001` starts deployable and unassigned after `prepare_fixtures.py`. The PHP version in `environment.json` identifies the runner's command-line PHP. These measurements apply to this test setup.

## Results
| Run | Users | p95 (ms) | p95 limit (ms) | Requests/s | Page loads | Unexpected failures | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1user-run1 | 1 | 61.7 | 1000 | 0.95 | 57 | 0 | PASS |
| 5user-run1 | 5 | 73.7 | 1500 | 4.70 | 282 | 0 | PASS |
| 1user-run2 | 1 | 63.7 | 1000 | 0.95 | 57 | 0 | PASS |
| 5user-run2 | 5 | 92.4 | 1500 | 4.67 | 280 | 0 | PASS |

All four runs met both limits. At five users, p95 increased to 73.7–92.4 ms and throughput reached 4.67–4.70 page loads per second.

## Honest notes
* Measured p95 stayed under 7% of the agreed limits. These thresholds would allow a moderate slowdown to pass.
* The one-second think time models technicians working at a desk and limits the request rate.
* A first attempt of the final pipeline reported every request as an unexpected failure because `PERF-001` had been left checked out by an earlier manual inspection, which makes the checkout form redirect to the list. The failure check did its job (a redirect is not a success); `prepare_fixtures.py` now always resets the performance laptop first.
* Fixed during development: k6 clears cookies between iterations by default, which logged the user out after one page; the script sets `noCookiesReset: true`.
