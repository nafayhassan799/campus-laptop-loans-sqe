# Requirements-to-tests traceability (final run)

Counts are passes over tests of that kind. XFAIL is a triaged defect whose test is expected to fail (see `findings.md`).

## Requirement coverage

| ID | Requirement | Tests by kind | Total | Unexpected failures |
| --- | --- | --- | ---: | ---: |
| CO-01 | Eligible student assignment recorded | browser 4/4, generated 35/35, performance 4/4, recovery 2/2, scenario 2/2 | 47 | 0 |
| CO-02 | Supplied expected return date persisted | browser 4/4, generated 7/7, scenario 2/2 | 13 | 0 |
| CO-03 | Checkout of an unavailable asset rejected, original record unchanged | generated 9/9, recovery 2/2, scenario 8/8 | 19 | 0 |
| CO-04 | 255-character asset-name limit enforced | generated 5/6 (+1 XFAIL) | 6 | 0 |
| CI-01 | Check-in clears assignee and return date | browser 5/5, generated 23/35 (+12 XFAIL), scenario 1/1 | 41 | 0 |
| CI-02 | Deployable return can be lent again | generated 6/8 (+2 XFAIL), scenario 1/1 | 9 | 0 |
| CI-03 | Repair return stays unavailable, cannot be lent | generated 6/8 (+2 XFAIL), scenario 2/2 | 10 | 0 |
| CI-04 | Repeated check-in records no second return | scenario 2/2 | 2 | 0 |

## Product-risk coverage

| ID | Risk | Tests by kind | Total | Unexpected failures |
| --- | --- | --- | ---: | ---: |
| R-A1 | Silent data truncation (asset name) | generated 10/12 (+2 XFAIL) | 12 | 0 |
| R-A2 | Unavailable or already-loaned laptop lent / overlapping loans | generated 1/1, scenario 8/8 | 9 | 0 |
| R-A3 | Rejection masked as HTTP 200 or ignored by clients | generated 12/12, scenario 4/4 | 16 | 0 |
| R-A4 | Unauthorised checkout or check-in | generated 2/2, scenario 2/2 | 4 | 0 |
| R-A5 | Repeated check-in duplicates return history | browser 4/4, generated 1/1, scenario 3/3 | 8 | 0 |
| R-A6 | Partial write or duplicate after a dependency failure | recovery 2/2 | 2 | 0 |
| R-A7 | Checkout form slow or unavailable under load | performance 4/4 | 4 | 0 |
| R-A8 | Invalid input persisted or silently coerced | browser 7/7, generated 75/90 (+15 XFAIL), scenario 3/3 | 100 | 0 |

## Test to requirement and risk (scenarios, browser, recovery, performance)

| Test | Kind | Requirements | Risks | Result |
| --- | --- | --- | --- | --- |
| S-CO-01 | scenario | CO-01 | R-A2 | PASS |
| S-CO-02a | scenario | CO-02 | R-A8 | PASS |
| S-CO-02b | scenario | CO-02 | R-A8 | PASS |
| S-CO-03a | scenario | CO-03 | R-A2, R-A3 | PASS |
| S-CO-03b | scenario | CO-03 | R-A2 | PASS |
| S-CO-03c | scenario | CO-03 | R-A2, R-A3 | PASS |
| S-CO-03d | scenario | CO-03 | R-A2 | PASS |
| S-CO-03e | scenario | CO-01, CO-03 | R-A8 | PASS |
| S-CI-01 | scenario | CI-01 | R-A5 | PASS |
| S-CI-02 | scenario | CI-02 | R-A2 | PASS |
| S-CI-03 | scenario | CI-03 | R-A2, R-A3 | PASS |
| S-CI-04a | scenario | CI-04 | R-A5, R-A3 | PASS |
| S-CI-04b | scenario | CI-04 | R-A5 | PASS |
| S-AUTH-01 | scenario | CO-03, CI-03 | R-A4 | PASS |
| S-AUTH-02 | scenario | CO-03 | R-A4 | PASS |
| S-CONC-01 | scenario | CO-03 | R-A2 | PASS |
| UC1-MAIN | browser | CO-01, CO-02 | R-A8 | PASS |
| UC1-ALT1 | browser | CO-01, CO-02 | R-A8 | PASS |
| UC1-ALT2 | browser | CO-01, CO-02 | R-A8 | PASS |
| UC1-EXC1 | browser | CO-01 | R-A8 | PASS |
| UC1-EXC2 | browser | CO-02 | R-A8 | PASS |
| UC2-MAIN | browser | CI-01 | R-A5 | PASS |
| UC2-ALT1 | browser | CI-01 | R-A5 | PASS |
| UC2-ALT2 | browser | CI-01 | R-A8 | PASS |
| UC2-EXC1 | browser | CI-01 | R-A5, R-A8 | PASS |
| UC2-EXC2 | browser | CI-01 | R-A5 | PASS |
| REC-history-write | recovery | CO-01, CO-03 | R-A6 | PASS |
| REC-db-outage | recovery | CO-01, CO-03 | R-A6 | PASS |
| PERF-1user-run1 | performance | CO-01 | R-A7 | PASS |
| PERF-5user-run1 | performance | CO-01 | R-A7 | PASS |
| PERF-1user-run2 | performance | CO-01 | R-A7 | PASS |
| PERF-5user-run2 | performance | CO-01 | R-A7 | PASS |

Generated cases (`CO.*`, `CI.*`) are mapped to requirements and risks field by field in `evidence/api-results.json` (`requirements` and `risks` on every case).
