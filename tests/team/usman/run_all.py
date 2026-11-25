"""One command, one exit code, for CI: Muhammad Usman's API, recovery, browser and performance checks.

    python -B tests/team/usman/run_all.py --admin-id 1                       # contract, generator, API, recovery, browser
    python -B tests/team/usman/run_all.py --admin-id 1 --stages perf         # k6 only (about 5 minutes)
    python -B tests/team/usman/run_all.py --admin-id 1 --stages contract,generate,api

Stages (run in this order): contract, generate, fixtures, api, recovery, browser, perf.
Exit code: 0 when every selected stage passes, 1 when any stage fails, 2 when a prerequisite is missing.
Environment for a Docker-free machine (see README.md): SQE_ARTISAN, SQE_DB_CMD, SQE_DB_STOP_CMD, SQE_DB_START_CMD,
SQE_CHROME_PATH. With the team's Docker stack the defaults of common.py apply and nothing needs to be set.
Each stage's console output is saved to output/usman/logs/<stage>.log.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOGS = ROOT / "output" / "usman" / "logs"
PY = [sys.executable, "-B"]
ALL = ["contract", "generate", "fixtures", "api", "recovery", "browser", "perf"]
DEFAULT = ["contract", "generate", "fixtures", "api", "recovery", "browser"]


def contract():
    try:
        from openapi_spec_validator import validate
    except ImportError:
        print("openapi-spec-validator is not installed (pip install openapi-spec-validator)")
        return 2
    validate(json.loads((HERE.parent / "hardware-loans.openapi.json").read_text(encoding="utf-8")))
    print("hardware-loans.openapi.json is a valid OpenAPI 3.0.3 document")
    return 0


def run(command, cwd=ROOT):
    return subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--admin-id", type=int, required=True)
    parser.add_argument("--stages", default=",".join(DEFAULT))
    args = parser.parse_args()
    stages = [s for s in ALL if s in args.stages.split(",")]
    LOGS.mkdir(parents=True, exist_ok=True)
    admin = str(args.admin_id)
    commands = {
        "generate": PY + [str(HERE / "api" / "generate_cases.py"), "--out", str(ROOT / "output" / "usman" / "api" / "cases.json")],
        "fixtures": PY + [str(HERE / "prepare_fixtures.py"), "--admin-id", admin],
        "api": PY + [str(HERE / "api" / "run_api_tests.py"), "--admin-id", admin],
        "recovery": PY + [str(HERE / "recovery" / "recover_checkout.py"), "--admin-id", admin],
        "perf": PY + [str(HERE / "perf" / "run_perf.py")],
    }
    results = {}
    for stage in stages:
        started = time.time()
        if stage == "contract":
            code, output = contract(), ""
        elif stage == "browser":
            browser = HERE / "browser"
            if not (browser / "node_modules").exists():
                subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=browser, capture_output=True)
            done = run(["npx", "playwright", "test"], cwd=browser)
            code, output = done.returncode, done.stdout
        else:
            done = run(commands[stage])
            code, output = done.returncode, done.stdout
        (LOGS / f"{stage}.log").write_text(output, encoding="utf-8")
        results[stage] = (code, time.time() - started)
        print(f"{'PASS' if code == 0 else 'FAIL'}  {stage:9} exit {code}  {results[stage][1]:6.1f}s  (log: output/usman/logs/{stage}.log)", flush=True)
        if stage in ("contract", "generate", "fixtures") and code != 0:
            break
    failed = [s for s, (c, _) in results.items() if c != 0]
    return 0 if not failed else 2 if any(results[s][0] == 2 for s in failed) else 1


if __name__ == "__main__":
    sys.exit(main())
