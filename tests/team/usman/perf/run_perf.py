"""Run the agreed k6 setups (1 user and 5 users, two runs each) and compare with limits.json.

    python -B tests/team/usman/perf/run_perf.py

Needs k6 on PATH (or K6=/path/to/k6) and output/usman/fixtures.json from prepare_fixtures.py.
Exit code 0 when every run is inside its limits, 1 when any p95 or unexpected-failure limit is
exceeded, 2 on setup errors. Raw k6 output and a comparison table are written to output/usman/perf/.
"""
import gzip
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / "output" / "usman" / "perf"
LIMITS = json.loads((HERE / "limits.json").read_text(encoding="utf-8"))


def run(command):
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True).stdout.strip()


def environment(k6):
    return {
        "k6": run([k6, "version"]), "python": platform.python_version(), "os": platform.platform(),
        "cpuCount": os.cpu_count(), "php": run(["php", "-r", "echo PHP_VERSION;"]) if shutil.which("php") else None,
        "phpWorkers": os.environ.get("PHP_CLI_SERVER_WORKERS"),
        "database": run(shlex.split(os.environ["SQE_DB_CMD"]) + ["-N", "-e", "select version()"]) if os.environ.get("SQE_DB_CMD") else None,
        "gitCommit": run(["git", "rev-parse", "HEAD"]), "snipeItPinned": "60fe07468534a283a473dbfe88244896b44c81bc",
        "limits": "tests/team/usman/perf/limits.json",
    }


def main():
    k6 = os.environ.get("K6") or shutil.which("k6")
    fixtures_file = ROOT / "output" / "usman" / "fixtures.json"
    if not k6 or not fixtures_file.exists():
        print("k6 or output/usman/fixtures.json is missing", file=sys.stderr)
        return 2
    data = json.loads(fixtures_file.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "environment.json").write_text(json.dumps(environment(k6), indent=2) + "\n", encoding="utf-8")
    rows, failed = [], False
    for number in range(1, LIMITS["runsPerSetup"] + 1):
        for key, setup in LIMITS["setups"].items():
            name = f"{setup['users']}user-run{number}"
            summary = OUT / f"{name}.summary.json"
            raw = OUT / f"{name}.raw.json"
            summary.unlink(missing_ok=True)
            raw.unlink(missing_ok=True)
            command = [k6, "run", "-q", "--out", f"json={raw}",
                       "-e", f"BASE_URL={data['baseUrl']}", "-e", f"USERNAME={data['technician']['username']}",
                       "-e", f"PASSWORD={data['technician']['password']}", "-e", f"ASSET_ID={data['assets']['perf']}",
                       "-e", f"VUS={setup['users']}", "-e", f"HOLD={LIMITS['holdSeconds']}", "-e", f"THINK={LIMITS['thinkTimeSeconds']}",
                       "-e", f"P95_MS={setup['p95_ms']}", "-e", f"MAX_FAIL={setup['unexpected_failure_rate']}",
                       "-e", f"SUMMARY={summary}", str(HERE / "checkout_form.js")]
            print(f"Running {name}: {setup['users']} user(s) for {LIMITS['holdSeconds']} s at target load ...", flush=True)
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            (OUT / f"{name}.stderr.txt").write_text(result.stderr, encoding="utf-8")
            if not raw.is_file() or not summary.is_file():
                print(f"{name}: k6 exited {result.returncode} without a complete report", file=sys.stderr)
                return 2
            with open(raw, "rb") as src, gzip.open(f"{raw}.gz", "wb") as dst:
                shutil.copyfileobj(src, dst)
            raw.unlink()
            result_data = json.loads(summary.read_text(encoding="utf-8"))
            latency = result_data["p95_ms"]
            ok = (result.returncode == 0 and result_data["thresholdsPassed"] and result_data["requests"] > 0
                  and latency is not None and latency < setup["p95_ms"]
                  and result_data["unexpectedFailureRate"] <= setup["unexpected_failure_rate"])
            failed |= not ok
            rows.append({"run": name, "users": setup["users"], "p95_ms": round(latency, 1) if latency is not None else None,
                         "p95_limit": setup["p95_ms"], "rps": round(result_data["requestsPerSecond"], 2),
                         "requests": result_data["requests"], "unexpected": result_data["unexpectedFailures"],
                         "result": "PASS" if ok else "FAIL"})
    (OUT / "comparison.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    lines = ["| Run | Users | p95 (ms) | p95 limit (ms) | Requests/s | Requests | Unexpected failures | Result |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    lines += [f"| {r['run']} | {r['users']} | {r['p95_ms']} | {r['p95_limit']} | {r['rps']} | {r['requests']} | {r['unexpected']} | {r['result']} |" for r in rows]
    (OUT / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
