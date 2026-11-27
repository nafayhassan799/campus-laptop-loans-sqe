# Rafay Imran: browser use cases, usability, accessibility and defensive security

Section A, 24I-3026. Campus Laptop Loans (Snipe-IT v8.8.4, upstream `60fe0746`; team base `ed3cb64d`).

| Deliverable | Where |
| --- | --- |
| Shared Playwright suite (config, seed, sign-in, reset, CI command) | [`../playwright/`](../playwright/README.md) |
| Use-case specification (UC-R1 keyboard checkout, UC-R2 repair return) | [`use-cases.md`](use-cases.md) |
| Use-case specs | `../playwright/rafay/uc-r1-keyboard-checkout.spec.cjs`, `uc-r2-repair-return.spec.cjs` |
| Usability checks, Lighthouse + axe findings, the checkout-screen fix, before/after | [`usability-accessibility.md`](usability-accessibility.md) |
| Accessibility scripts | `../playwright/rafay/a11y/axe-scan.spec.cjs`, `lighthouse.mjs`, `set_header_color.sh` |
| Route/data inventory, access matrix, ZAP, controls review, dependency audit | [`security-assessment.md`](security-assessment.md) |
| Access-matrix spec | `../playwright/rafay/access-matrix.spec.cjs` |
| Defects, root cause analysis, risk register input, exit criteria, traceability, notes for the team | [`findings-risks-traceability.md`](findings-risks-traceability.md) |
| Hours and AI-use record | [`hours-and-ai-use.md`](hours-and-ai-use.md) |
| Raw evidence | `evidence/playwright/` (combined HTML report, JUnit, JSON results), `evidence/a11y/{before,after,docker-before,docker-after}/`, `evidence/zap/`, `evidence/deps/`, `evidence/security/access-matrix.json` |

## Results at a glance (final run 2026-11-25)

* Combined suite on the Docker build (2026-11-27): **29 passed, 0 failed**. 3 repeated runs: 83/83. The open defects DEF-R1 and DEF-R2 are tracked by tests that pass only while that exact defect is present (see `use-cases.md`).
* Use cases: UC-R1 and UC-R2, each with a main flow, 2 alternative flows and 2–3 exception flows. Every flow asserts the visible outcome and the saved state through REST read-back.
* Accessibility: checkout screen Lighthouse **87 → 100**, axe **4 → 0** serious rules (23 → 0 nodes), on both the native stack and the Docker build (`evidence/a11y/docker-*`). Checkin improved 87 → 93 as a side effect.
* Security: 11/11 access decisions as expected. ZAP passive found 0 High and 6 Medium alert types, triaged. composer audit found 1 advisory (not reachable); npm audit found 51, mostly build-only tooling; the shipped ones are Bootstrap 3.4.1 and SheetJS 0.18.5. ZAP also found a Bootstrap 3.3.4 copy (through `bootstrap-less`) that npm audit misses.
* Defects found: DEF-R1 (due date silently set to "now", S2), DEF-R2 (raw validation key), U-03 (lost input on a check-in rejection), A11Y-01 (login label), SEC-01…07.

## Re-run (viva)

```bash
cd tests/team/playwright
export SQE_CHROME_PATH=/opt/pw-browsers/chromium   # only if Playwright's own Chromium is not installed
python3 -B seed.py --admin-id 1
npx playwright test --project=rafay -g "UC-R1-MAIN"   # keyboard task
npx playwright test --project=rafay -g "AC-07"        # a denied role check
npx playwright show-report ../../../output/playwright/html
```

Note on the commits: the accessibility fix (`resources/views/...`, `resources/lang/en-US/general.php`) is the only change to application code. Everything else is under `tests/team/`.
