# Effort log and AI-use record (Muhammad Usman, 24I-3031)

The member must replace the "Actual" column with the hours really spent and confirm each AI-use entry before submission. Nothing below states hours the member worked.

## Estimate versus actual

| Work package | Optimistic | Most likely | Pessimistic | PERT expected (O+4M+P)/6 | Actual (member to fill) |
| --- | ---: | ---: | ---: | ---: | ---: |
| OpenAPI and case generator | 7 h | 10 h | 13 h | 10.0 h | |
| API and integration suite | 5 h | 7 h | 10 h | 7.2 h | |
| k6 and controlled recovery | 5 h | 7 h | 10 h | 7.2 h | |
| Two browser use cases | 6 h | 7 h | 9 h | 7.2 h | |
| Traceability, evidence and viva preparation | 4 h | 5 h | 7 h | 5.2 h | |
| **Total** | **27 h** | **36 h** | **49 h** | **36.7 h** | |

Agent wall-clock for drafting and running this work in one session was roughly one hour; reading, verifying and being able to explain it in the viva is the member's time and is not in that figure.

## AI-use record

| # | Tool | Purpose | Output | What was checked or changed |
| --- | --- | --- | --- | --- |
| 1 | Claude Code (Claude Sonnet 5.5), session linked in the commit trailers | Read the assignment, the repository and the pinned controllers; verify the starter OpenAPI file against the code | `api-test-basis.md`, corrected `hardware-loans.openapi.json` | Every response code and rule was probed on the running app; the starter's 404/422 claims were wrong and replaced; the contract passes `openapi-spec-validator` |
| 2 | same | Implement the spec-driven generator | `api/generate_cases.py`, `api/spec_change_demo.py` | Ran on the real spec (100 cases) and on a changed copy (6 removed, 6 added); two oracle bugs found while running (null on the server-inferred field, reference-key boundaries) and fixed |
| 3 | same | Implement the API runner and scenarios | `api/run_api_tests.py`, `api/common.py`, `api/known-defects.json` | Compared against the team smoke test (unchanged, passes); regression check by narrowing `assets.name` back to 191 characters reproduced the original truncation; a history-paging bug in the helper (500-row cutoff) found and fixed; each XFAIL was reproduced by hand before being listed |
| 4 | same | k6 script and runner | `perf/*` | Found and fixed the k6 cookie reset between iterations that logged users out; limits file written before any measured run; four raw runs kept |
| 5 | same | Recovery script | `recovery/recover_checkout.py` | Fixed the SQL delimiter and the failure classification after the first runs; both faults pass |
| 6 | same | Playwright use cases | `browser/*` | Explored the real forms first; discovered that `fill()` without focus breaks the picker and that flash messages are lost to background requests; fixed the helpers; ran the 10 tests five times in a row |
| 7 | same | Findings, issue drafts, traceability | `findings.md`, `issue-drafts.md`, `build_traceability.py` | Statements about root cause were rechecked against the source (`Schema::defaultStringLength(191)`, the check-in controller); two unsupported claims were removed |

Prompts: the single instruction was "complete all of my assigned tasks" with the assignment file and the repository link. Keep the full prompt history from the session with this record.
Not done by AI and still needed from the member: filing the GitHub issues, pushing and opening the pull request, the actual-hours column, and rehearsing the viva.
