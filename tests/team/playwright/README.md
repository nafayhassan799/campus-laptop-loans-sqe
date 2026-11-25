# Shared team Playwright suite

Owner: Rafay Imran (Section A, 24I-3026). Used by all three members for the browser use cases.

One Chromium configuration, one seed script, one stored sign-in per role and one combined report.
Each member keeps their specs in their own folder and gets a Playwright project of the same name.

| File | Purpose |
| --- | --- |
| `playwright.config.cjs` | Chromium, 1 worker, list + JUnit + JSON + HTML reporters into `output/playwright/`, optional ZAP proxy |
| `seed.py` | Creates or refreshes the technician and reviewer logins, students, status labels, model and one laptop per test |
| `auth.setup.cjs` | Signs each role in once and stores the session in `output/playwright/.auth/` |
| `support/fixtures.cjs` | `technician` and `reviewer` page fixtures, `resetAsset`, `loanAsset`, `readAsset`, `history`, `choose` (select2 with the mouse), `keyboardChoose`, `tabTo`, `focused` |
| `rafay/` | Rafay's use cases, access matrix and accessibility scans |

Credentials, API tokens and stored sessions are written only to `output/playwright/` (git-ignored, mode 600).
`seed.py` creates new passwords on every run, so nothing secret is kept between runs.

## Run it

You need the local synthetic Snipe-IT instance on <http://localhost:8000>, with the asset-name migration applied.
The Docker stack is `tests/team/start-local.ps1`. Without Docker, use `tests/team/usman/start_native.sh` on Usman's branch.
Complete the first-run admin once, then:

```bash
cd tests/team/playwright
npm ci                                                       # Playwright 1.61.1, @axe-core/playwright, Lighthouse
npx playwright install chromium                              # or: export SQE_CHROME_PATH=/path/to/chromium
python3 -B seed.py --admin-id 1                              # 1 = the first-run admin's user id
npx playwright test                                          # setup + every project: the combined suite for CI
npx playwright test --project=rafay                          # one owner's tests
npx playwright show-report ../../../output/playwright/html   # the combined HTML report
```

For the Docker stack, the seed creates its API tokens with
`SQE_ARTISAN="docker compose -p sqe-campus-laptops exec -T -u docker app php artisan"`.

Exit code 0 means every test passed or failed as expected (`test.fail()` marks a known open defect).
Exit code 1 means an unexpected failure, or a known defect test that started passing: remove its `test.fail()` once the fix lands.

## Reset between runs

* Every test resets its own laptop first. `resetAsset` checks it in if it is loaned, then sets "SQE Ready to Deploy", no name and no due date. `loanAsset` resets it and then lends it to Sara through the API.
* Re-running `seed.py` is safe. It reuses existing records and only refreshes the two passwords and the tokens.
* For a completely clean state, recreate the database, complete the first-run admin again and re-run `seed.py`.

## Rules for adding your own use cases (Nafay, Usman)

1. Put your specs in `tests/team/playwright/<owner>/` and add a project in `playwright.config.cjs`:
   `{ name: 'nafay', testDir: './nafay', testMatch: /.*\.spec\.cjs/, dependencies: ['setup'] }`.
2. Add one asset tag per test that changes a loan to `ASSET_TAGS` in `seed.py`, so no two tests share a laptop.
3. Import helpers from `../support/fixtures.cjs` and use the `technician` / `reviewer` fixtures instead of signing in yourself.
4. Prefer roles, labels and visible text for selectors. Confirm the postcondition with `readAsset` or `history` (REST read-back) or with a separate page load.
5. Tests that change a global setting (for example Usman's "notes required") must restore it in a `finally` block. The suite runs with one worker.

## Routing the browser traffic through OWASP ZAP (passive scan only)

```bash
zap.sh -daemon -host 127.0.0.1 -port 8090 -config api.disablekey=true
SQE_ZAP_PROXY=http://127.0.0.1:8090 npx playwright test --project=rafay
```

Only the browser suite goes through ZAP. The API suites keep calling the app directly.
