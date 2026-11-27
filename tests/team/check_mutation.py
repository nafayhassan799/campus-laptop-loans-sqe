"""Reject a quality run if either custom loan-rule mutant survives."""

import json
from pathlib import Path


REPORT = Path(__file__).resolve().parents[2] / "output" / "nafay-quality" / "infection.json"
OPERATORS = {
    "Sqe\\Mutation\\AvailabilityUsesPendingFlag",
    "Sqe\\Mutation\\ReintroduceAssetNameTruncation",
}


def main():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    for operator in sorted(OPERATORS):
        killed = [
            mutant for mutant in report["killed"]
            if mutant["mutator"]["mutatorName"] == operator
        ]
        unexpected = [
            mutant for bucket in ("escaped", "timeouted", "errored", "syntaxErrors", "uncovered")
            for mutant in report[bucket]
            if mutant["mutator"]["mutatorName"] == operator
        ]
        if unexpected or not killed or any("Failed asserting" not in mutant["processOutput"] for mutant in killed):
            raise SystemExit(f"{operator} must be detected by a test assertion")
        print(f"{operator}: {len(killed)} detected by test assertions")


if __name__ == "__main__":
    main()
