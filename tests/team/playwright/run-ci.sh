#!/usr/bin/env bash
# One command, one exit code for the combined browser suite (hand-off to Nafay's CI gate).
#
#   bash tests/team/playwright/run-ci.sh <admin-id>
#
# Needs the local synthetic stack on http://localhost:8000 with the first-run admin created.
# Exit 0: every test passed (open-defect tests pass only while their exact defect is present).
# Non-zero: any failed test, a setup error, or an open defect that now looks fixed. Report: output/playwright/{html,junit.xml,results.json}.
# Upload output/playwright/ as the CI artifact EXCEPT fixtures.json and .auth/ (local credentials).
set -euo pipefail
ADMIN_ID="${1:?usage: run-ci.sh <admin-id>}"
cd "$(dirname "$0")"
npm ci --no-audit --no-fund
if [ -z "${SQE_CHROME_PATH:-}" ]; then
  npx playwright install --with-deps chromium
fi
python3 -B seed.py --admin-id "$ADMIN_ID"
npx playwright test
