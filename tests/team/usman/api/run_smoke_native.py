"""Run the team's unchanged smoke test against an instance without Docker.

Usage: SQE_ARTISAN="php artisan" python -B tests/team/usman/api/run_smoke_native.py --admin-id 1
"""
from contextlib import ExitStack
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

common.smoke.local_api = common.local_api  # only the token source changes; every assertion is the team's

parser = argparse.ArgumentParser()
parser.add_argument("--admin-id", type=int, required=True)
args = parser.parse_args()
with ExitStack() as sessions:
    admin = sessions.enter_context(common.local_api(args.admin_id, "SQE smoke"))
    common.smoke.run(admin, sessions)
