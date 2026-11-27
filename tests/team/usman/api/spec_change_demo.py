"""Viva demonstration: change two constraints in a copy of the spec, regenerate, show what moves.

    python -B tests/team/usman/api/spec_change_demo.py

Needs no Docker and no running application. The real contract is never modified. Changes applied to the copy:
  1. checkout name maxLength 255 -> 100   (the 254/255/256 trio becomes 99/100/101)
  2. checkout assigned_user minimum 1 -> 10 (the 0/1/2 trio becomes 9/10/11)
Writes before/after case files and spec-change-report.md to output/usman/api/spec-change/.
"""
import copy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate_cases  # noqa: E402

SPEC = HERE.parents[1] / "hardware-loans.openapi.json"
OUT = HERE.parents[3] / "output" / "usman" / "api" / "spec-change"

original = generate_cases.load(SPEC)
changed = copy.deepcopy(original)
fields = changed["paths"]["/hardware/{asset_id}/checkout"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]
fields["name"]["maxLength"] = 100
fields["assigned_user"]["minimum"] = 10

before = {c["id"]: c for c in generate_cases.generate(original)}
after = {c["id"]: c for c in generate_cases.generate(changed)}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "cases-before.json").write_text(json.dumps(list(before.values()), indent=2) + "\n", encoding="utf-8")
(OUT / "cases-after.json").write_text(json.dumps(list(after.values()), indent=2) + "\n", encoding="utf-8")
(OUT / "hardware-loans.changed.openapi.json").write_text(json.dumps(changed, indent=2) + "\n", encoding="utf-8")


def show(case):
    body = {k: (f"{'L' * 3}...({len(v)} chars)" if isinstance(v, str) and set(v) == {"L"} and len(v) > 20 else v) for k, v in case["body"].items()}
    return f"`{case['id']}` expects **{case['expect']['outcome']}**, body {json.dumps(body)}"


removed = sorted(set(before) - set(after))
added = sorted(set(after) - set(before))
modified = sorted(i for i in set(before) & set(after) if before[i] != after[i])
lines = ["# Spec-change demonstration", "",
         "Two constraints were changed in a copy of `hardware-loans.openapi.json`; the generator was run on both.", "",
         "| Constraint | Before | After |", "| --- | --- | --- |",
         "| checkout `name` maxLength | 255 | 100 |", "| checkout `assigned_user` minimum | 1 | 10 |", "",
         f"Cases before: {len(before)}. Cases after: {len(after)}. Removed: {len(removed)}. Added: {len(added)}. Modified in place: {len(modified)}.", ""]
for title, ids, source in (("Removed (only in the original spec)", removed, before), ("Added (only in the changed spec)", added, after)):
    lines += [f"## {title}", ""] + [f"- {show(source[i])}" for i in ids] + [""]
lines += ["## Modified in place", ""]
for i in modified:
    lines.append(f"- `{i}`: expectation {before[i]['expect']} -> {after[i]['expect']}; body {json.dumps({k: v for k, v in before[i]['body'].items() if before[i]['body'][k] != after[i]['body'].get(k)}, default=str)[:60]} -> "
                 f"{json.dumps({k: v for k, v in after[i]['body'].items() if before[i]['body'].get(k) != v}, default=str)[:60]}")
lines += ["", "## What this means for the tests", "",
          "* A 255-character name was valid and is now invalid, so `...length-255-at-maximum` is replaced by `...length-100-at-maximum` and the 256-character rejection case becomes a 101-character one. "
          "The API must now reject 101 characters with HTTP 200 and status `error`, and the saved asset must keep its previous name, borrower, due date, status, counters and history.",
          "* With minimum 10, user id 9 is the below-minimum rejection and 10 and 11 become the boundary neighbours; because user ids are table keys, whether 10 and 11 succeed depends on those users existing (the runner asks the API).", ""]
(OUT / "spec-change-report.md").write_text("\n".join(lines), encoding="utf-8")
print(f"before {len(before)} cases, after {len(after)}: {len(removed)} removed, {len(added)} added, {len(modified)} modified -> {OUT / 'spec-change-report.md'}")
