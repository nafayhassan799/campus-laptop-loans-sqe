"""Build the requirements-to-tests matrix from the raw results of a run.

    python -B tests/team/usman/build_traceability.py

Reads output/usman/api/results.json, output/usman/browser/junit.xml, output/usman/perf/comparison.json and
output/usman/recovery/recovery-results.json; writes tests/team/usman/evidence/traceability-matrix.md.
"""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "output" / "usman"
REQ = {"CO-01": "Eligible student assignment recorded", "CO-02": "Supplied expected return date persisted",
       "CO-03": "Checkout of an unavailable asset rejected, original record unchanged", "CO-04": "255-character asset-name limit enforced",
       "CI-01": "Check-in clears assignee and return date", "CI-02": "Deployable return can be lent again",
       "CI-03": "Repair return stays unavailable, cannot be lent", "CI-04": "Repeated check-in records no second return"}
RISK = {"R-A1": "Silent data truncation (asset name)", "R-A2": "Unavailable or already-loaned laptop lent / overlapping loans",
        "R-A3": "Rejection masked as HTTP 200 or ignored by clients", "R-A4": "Unauthorised checkout or check-in",
        "R-A5": "Repeated check-in duplicates return history", "R-A6": "Partial write or duplicate after a dependency failure",
        "R-A7": "Checkout form slow or unavailable under load", "R-A8": "Invalid input persisted or silently coerced"}
BROWSER = {"UC1-MAIN": (["CO-01", "CO-02"], ["R-A8"]), "UC1-ALT1": (["CO-01", "CO-02"], ["R-A8"]), "UC1-ALT2": (["CO-01", "CO-02"], ["R-A8"]),
           "UC1-EXC1": (["CO-01"], ["R-A8"]), "UC1-EXC2": (["CO-02"], ["R-A8"]),
           "UC2-MAIN": (["CI-01"], ["R-A5"]), "UC2-ALT1": (["CI-01"], ["R-A5"]), "UC2-ALT2": (["CI-01"], ["R-A8"]),
           "UC2-EXC1": (["CI-01"], ["R-A5", "R-A8"]), "UC2-EXC2": (["CI-01"], ["R-A5"])}
STATIC = [("REC-history-write", ["CO-01", "CO-03"], ["R-A6"]), ("REC-db-outage", ["CO-01", "CO-03"], ["R-A6"]),
          ("PERF-1user x2, PERF-5user x2", ["CO-01"], ["R-A7"])]


def main():
    api = json.loads((OUT / "api" / "results.json").read_text(encoding="utf-8"))
    rows = []  # (test id, kind, requirements, risks, status)
    for r in api["results"]:
        rows.append((r["id"], r["kind"], r.get("requirements", []), r.get("risks", []), r["status"]))
    junit = ET.parse(OUT / "browser" / "junit.xml").getroot()
    for case in junit.iter("testcase"):
        key = next((k for k in BROWSER if k in case.get("name", "")), None)
        failed = case.find("failure") is not None or case.find("error") is not None
        if key:
            rows.append((key, "browser", *BROWSER[key], "FAIL" if failed else "PASS"))
    recovery = {r["mode"]: r["result"] for r in json.loads((OUT / "recovery" / "recovery-results.json").read_text(encoding="utf-8"))}
    rows.append(("REC-history-write", "recovery", ["CO-01", "CO-03"], ["R-A6"], "PASS" if recovery.get("history-write") == "PASS" else "FAIL"))
    rows.append(("REC-db-outage", "recovery", ["CO-01", "CO-03"], ["R-A6"], "PASS" if recovery.get("db-outage") == "PASS" else "FAIL"))
    perf = json.loads((OUT / "perf" / "comparison.json").read_text(encoding="utf-8"))
    for p in perf:
        rows.append((f"PERF-{p['run']}", "performance", ["CO-01"], ["R-A7"], p["result"]))

    def tally(ident, field):
        mine = [r for r in rows if ident in r[field]]
        kinds = {}
        for r in mine:
            kinds.setdefault(r[1], []).append(r[4])
        cells = ", ".join(f"{k} {sum(1 for s in v if s == 'PASS')}/{len(v)}" + (f" (+{sum(1 for s in v if s == 'XFAIL')} XFAIL)" if "XFAIL" in v else "") for k, v in sorted(kinds.items()))
        bad = sum(1 for r in mine if r[4] in ("FAIL", "XPASS"))
        return cells or "none", len(mine), bad

    lines = ["# Requirements-to-tests traceability (final run)", "",
             "Counts are passes over tests of that kind. XFAIL is a triaged defect whose test is expected to fail (see `findings.md`).", "",
             "## Requirement coverage", "", "| ID | Requirement | Tests by kind | Total | Unexpected failures |", "| --- | --- | --- | ---: | ---: |"]
    for rid, text in REQ.items():
        cells, total, bad = tally(rid, 2)
        lines.append(f"| {rid} | {text} | {cells} | {total} | {bad} |")
    lines += ["", "## Product-risk coverage", "", "| ID | Risk | Tests by kind | Total | Unexpected failures |", "| --- | --- | --- | ---: | ---: |"]
    for rid, text in RISK.items():
        cells, total, bad = tally(rid, 3)
        lines.append(f"| {rid} | {text} | {cells} | {total} | {bad} |")
    lines += ["", "## Test to requirement and risk (scenarios, browser, recovery, performance)", "", "| Test | Kind | Requirements | Risks | Result |", "| --- | --- | --- | --- | --- |"]
    for r in rows:
        if r[1] != "generated":
            lines.append(f"| {r[0]} | {r[1]} | {', '.join(r[2])} | {', '.join(r[3])} | {r[4]} |")
    lines += ["", "Generated cases (`CO.*`, `CI.*`) are mapped to requirements and risks field by field in `evidence/api-results.json` (`requirements` and `risks` on every case)."]
    target = ROOT / "tests" / "team" / "usman" / "evidence"
    target.mkdir(parents=True, exist_ok=True)
    (target / "traceability-matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:30]))


if __name__ == "__main__":
    main()
