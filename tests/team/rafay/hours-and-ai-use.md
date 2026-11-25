# Actual hours and AI-use record (Rafay Imran)

## Effort: estimate versus actual

The three-point estimates come from the project brief. PERT expected = (O + 4M + P) / 6.
**Rafay: fill in the "Actual" column with your own hours** (include your verification, re-runs and viva preparation). Do not use the agent's run time as your hours.

| Work package | O | M | P | PERT | Actual (h) | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Shared Playwright configuration and own use cases | 6 | 8 | 11 | 8.2 | | |
| Usability, accessibility and the screen fix | 6 | 8 | 11 | 8.2 | | |
| Defensive assessment and dependency audit | 6 | 8 | 11 | 8.2 | | |
| Integrating and validating the shared browser suite | 6 | 8 | 10 | 8.0 | | |
| Evidence, risk register and viva preparation | 4 | 5 | 7 | 5.2 | | |
| **Total** | **28** | **37** | **50** | **37.7** | | |

## AI-use record

Tool: Claude Code (Anthropic), run as an agent in a cloud container on 2026-11-25 with access to a clone of the team repository.
Prompt (kept verbatim): *"I want you to complete all my tasks for me"*. It was given the member brief `rafay-imran.txt` and the course handout `SQE_Final_Project_Fall_2026.pdf`.
The agent wrote the six commits on branch `sqe/rafay-browser-a11y-security`; Rafay reviewed them and pushed them under his own account.

| # | Purpose | AI output | What the agent verified | What Rafay checked or changed (fill in) |
| --- | --- | --- | --- | --- |
| 1 | Local environment | Native start (MariaDB + `php -S`, Usman's launcher) and first-run admin (Nafay's initializer) | App served on :8000, asset-name column `varchar(255)` (migration applied) | |
| 2 | Shared Playwright suite | `playwright.config.cjs`, `seed.py`, `auth.setup.cjs`, `support/fixtures.cjs`, `run-ci.sh` | Seed is idempotent (run 3 times); DB permissions checked; the report was scanned for passwords and tokens (one leak found and fixed: the password moved out of `fill` step titles); `run-ci.sh` runs end to end with exit 0 | |
| 3 | UC-R1 / UC-R2 specs | 2 use cases × (main + 2 alt + 2–3 exc) + 2 known-defect tests | Each flow observed by hand before asserting; both `test.fail` tests checked to fail at the intended assertion; Rafay project repeated 3× before AC-11 was added (71/71), final combined run 29/29 as expected; two test-timing bugs found and fixed (select2 focus, paginated history) | |
| 4 | Accessibility | axe spec, Lighthouse script, checkout fix (Blade + layout + branding setting) | Before/after run on the same viewport, data and machine; use-case suite re-run after the fix; screenshot checked for visual regressions (footer underline corrected) | |
| 5 | Security | Access-matrix spec (11 decisions), ZAP passive run, cookie/CSRF/policy source review, composer/npm audit triage | Every observation backed by a raw file or a source line; CSRF assertion corrected after observing 302 (not 419) and reading `Handler.php`; `bootstrap-less` origin confirmed through the source map | |
| 6 | Documents | `use-cases.md`, `usability-accessibility.md`, `security-assessment.md`, `findings-risks-traceability.md`, this file | Numbers copied from the raw evidence files | |

Points to be able to explain at the viva (re-run them yourself first):

* `npx playwright test --project=rafay -g "UC-R1-MAIN"`: how `tabTo`/`focused` prove the focus order, and how `readAsset` and `history` prove the saved loan.
* `npx playwright test --project=rafay -g "AC-07"`: why 403 *plus* an unchanged `checkout_counter` proves the denial.
* A before/after accessibility finding, e.g. A11Y-02: open `evidence/a11y/before/axe-checkout.json` and `after/axe-checkout.json`, then the fix in `checkout.blade.php`.
* Why `available_actions.checkout` is not proof of availability, and `user_can_checkout` is.
