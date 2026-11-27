"""Execute generated and scenario API tests for laptop checkout and check-in.

    SQE_ARTISAN="php artisan" python -B tests/team/usman/api/run_api_tests.py --admin-id 1

Exit code 0 when every test passes (or fails only as a documented, triaged defect listed in
known-defects.json), 1 when any unexpected failure or any fixed defect still marked as known
(XPASS) is found, 2 for setup errors. Results are written to output/usman/api/:
results.json, junit.xml and summary.md.

Every operation is followed by a fresh GET of the asset and a read of its activity history.
A rejected request must leave the asset record and its history exactly as they were.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import date
import json
from pathlib import Path
import sys
import time
import traceback
from xml.sax.saxutils import quoteattr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import generate_cases  # noqa: E402

HERE = Path(__file__).resolve().parent
SPEC = HERE.parents[1] / "hardware-loans.openapi.json"
KNOWN = HERE / "known-defects.json"
OUT = common.OUTPUT / "api"
GEN_TAG, FLOW_TAG = "API-GEN-001", "API-FLOW-001"


class Failure(AssertionError):
    pass


class ReproducedDefect(Failure):
    def __init__(self, issue, observed):
        super().__init__(f"{issue}: confirmed the documented response and saved state")
        self.issue = issue
        self.observed = observed


def expect(condition, message):
    if not condition:
        raise Failure(message)


def classify(status, body):
    if status == 200 and isinstance(body, dict):
        if body.get("status") == "success":
            return "accepted"
        if body.get("status") == "error":
            return "rejected"
    if status in (400, 404, 422):
        return "rejected"
    if status in (401, 403):
        return "forbidden"
    return "server-error"


class Context:
    def __init__(self, admin, tech, reviewer, fx):
        self.admin, self.tech, self.reviewer, self.fx = admin, tech, reviewer, fx
        self.archived = admin.fixture("statuslabels", "name", "SQE Archived", type="archived")
        self.today = date.today().isoformat()
        self.due = common.due_date(7)
        self.boundary_assets = fx.boundary_assets()
        self.gen_asset = fx.asset(GEN_TAG)
        self.flow_asset = fx.asset(FLOW_TAG)

    # ------------------------------------------------------------------ fixtures
    def tokens(self):
        return {"@asset": self.gen_asset, "@student": self.fx.student_one, "@due_date": self.due, "@today": self.today,
                "@deployable_status": self.fx.ready["id"], "@repair_status": self.fx.repair["id"],
                "@location": self.fx.location["id"]}

    def resolve(self, value, asset_id):
        tokens = self.tokens()
        tokens["@asset"] = asset_id
        if isinstance(value, str) and value in tokens:
            return tokens[value]
        if isinstance(value, dict):
            return {k: self.resolve(v, asset_id) for k, v in value.items()}
        return value

    def reset(self, asset_id):
        return common.reset_asset(self.tech, asset_id, self.fx.ready["id"])

    def loan(self, asset_id, student=None, due=None):
        body = {"checkout_to_type": "user", "assigned_user": student or self.fx.student_one}
        if due:
            body["expected_checkin"] = due
        self.tech.save(f"hardware/{asset_id}/checkout", body)

    # ------------------------------------------------------------------- read back
    def snap(self, asset_id):
        a = self.admin.request("GET", f"hardware/{asset_id}")
        events = common.history(self.admin, asset_id)
        return {
            "name": a["name"], "assigned": (a["assigned_to"] or {}).get("id"),
            "due": (a["expected_checkin"] or {}).get("datetime", "")[:10] or None,
            "status": a["status"]["id"], "meta": a["status"].get("status_meta"),
            "location": (a["location"] or {}).get("id"),
            "out": a["checkout_counter"], "in": a["checkin_counter"],
            "last_out": (a["last_checkout"] or {}).get("datetime"), "last_in": (a["last_checkin"] or {}).get("datetime"),
            "events": [e["id"] for e in events],
            "checkouts": common.count_actions(events, common.CHECKOUT),
            "checkins": common.count_actions(events, common.CHECKIN),
            "raw_events": events,
        }

    def unchanged(self, before, after, label="Rejected request"):
        for field in ("name", "assigned", "due", "status", "location", "out", "in", "last_out", "last_in", "events"):
            expect(before[field] == after[field], f"{label} changed {field}: {before[field]!r} -> {after[field]!r}")

    def reference_exists(self, reference, ident):
        table = reference.split(":")[0]
        status, body = common.raw(self.admin, "GET", f"{table}/{ident}")
        if status == 404 or (status == 200 and isinstance(body, dict) and body.get("status") == "error"):
            return False
        expect(status == 200 and isinstance(body, dict) and body.get("id") == ident,
               f"Could not read {table}/{ident}: HTTP {status}")
        if reference == "statuslabels:deployable":
            return body.get("type") == "deployable"
        return True


# =================================================================== generated cases
def run_generated(ctx, case, defect=None):
    asset_id = ctx.gen_asset if case["asset_id"] == "@asset" else case["asset_id"]
    fixture_id = ctx.gen_asset
    body = ctx.resolve(case["body"], asset_id)
    expected = case["expect"]["outcome"]
    if expected == "depends":
        path_boundary = case["field"] == "asset_id"
        value = asset_id if path_boundary else body[case["field"]]
        reference = case["expect"]["oracle"].split("reference:", 1)[1]
        expected = "accept" if ctx.reference_exists(reference, value) else "reject"
        if path_boundary and expected == "accept":
            expect(asset_id in ctx.boundary_assets, f"Asset {asset_id} is not a disposable boundary fixture")
            fixture_id = asset_id

    ctx.reset(fixture_id)
    if case["precondition"] == "loaned":
        ctx.loan(fixture_id, due=ctx.due)
    if defect and defect["issue"] == "D-API-03":
        ctx.admin.request("PATCH", f"hardware/{fixture_id}", {"name": "SQE retained name"})
    before = ctx.snap(fixture_id)
    path = f"hardware/{asset_id}/{case['path'].rsplit('/', 1)[1]}"
    status, response = common.raw(ctx.tech, "POST", path, body)
    outcome = classify(status, response)
    envelope = response if isinstance(response, dict) else {}
    observed = {"http": status, "bodyStatus": envelope.get("status"),
                "message": json.dumps(envelope.get("messages"))[:160], "outcome": outcome}
    after = ctx.snap(fixture_id)

    if expected == "reject":
        if defect and outcome == "accepted":
            verify_known_defect(ctx, defect, case, body, before, after, observed)
        expect(outcome == "rejected", f"expected a rejection, got {outcome} (HTTP {status}, {observed['message']})")
        ctx.unchanged(before, after)
    else:
        expect(outcome == "accepted", f"expected success, got {outcome} (HTTP {status}, {observed['message']})")
        assert_effects(ctx, case, body, before, after)
    return observed


def date_part(value):
    return None if value in (None, "") else str(value)[:10]


def verify_known_defect(ctx, defect, case, body, before, after, observed):
    issue = defect["issue"]
    expected_body = dict(body)
    if issue == "D-API-01":
        latest = next(event for event in reversed(after["raw_events"]) if event["action"] == common.CHECKIN)
        expect(str(latest["date"]).split(" ", 1)[0] == "-0001-11-30",
               f"Unexpected invalid-date signature: {latest['date']!r}")
        del expected_body["checkin_at"]
    elif issue == "D-API-02":
        field = case["field"]
        stored_field = {"status_id": "status", "location_id": "location"}[field]
        value = body[field]
        coerced = None if value in (0, "abc") else 1 if value is True else 2
        expect(after[stored_field] == coerced, f"Unexpected {field} coercion: {after[stored_field]!r}")
        expected_body[field] = coerced
    elif issue == "D-API-03":
        expect(before["name"] == "SQE retained name" and after["name"] == before["name"],
               "Invalid clear_name did not preserve the seeded name")
    elif issue == "D-API-04":
        expected_body["name"] = str(body["name"])
    else:
        raise Failure(f"No saved-state check for {issue}")
    assert_effects(ctx, case, expected_body, before, after)
    raise ReproducedDefect(issue, observed)


def assert_effects(ctx, case, body, before, after):
    if case["operation"] == "checkoutLaptopToStudent":
        expect(after["assigned"] == body["assigned_user"], "borrower not persisted")
        expect(after["meta"] and after["meta"].casefold() == "deployed", f"asset not deployed ({after['meta']})")
        expect(after["out"] == before["out"] + 1, "checkout counter did not increase by one")
        expect(after["checkouts"] == before["checkouts"] + 1, "history did not gain exactly one checkout entry")
        expect(after["due"] == date_part(body.get("expected_checkin")), f"expected_checkin {after['due']!r} != {body.get('expected_checkin')!r}")
        if isinstance(body.get("name"), str):
            expect(after["name"] == body["name"], f"name was not persisted in full ({len(str(after['name']))} of {len(body['name'])} chars)")
        elif "name" in body and body["name"] is None:
            expect(after["name"] in (None, ""), f"explicit null name left {after['name']!r}")
        if "name" not in body:
            expect(after["name"] == before["name"], "omitted name changed the stored name")
    else:
        expect(after["assigned"] is None and after["due"] is None, "return did not clear assignee and due date")
        expect(after["in"] == before["in"] + 1, "check-in counter did not increase by one")
        expect(after["checkins"] == before["checkins"] + 1, "history did not gain exactly one check-in entry")
        if "status_id" in body:
            expect(after["status"] == body["status_id"], f"return status {after['status']} != {body['status_id']}")
        if isinstance(body.get("name"), str):
            expect(after["name"] == body["name"], "name not persisted in full")
        if body.get("clear_name") == "1":
            expect(after["name"] in (None, ""), "clear_name did not clear the name")
        if body.get("location_id"):
            expect(after["location"] == body["location_id"], "return location not persisted")
        if body.get("checkin_at") and body["checkin_at"] != ctx.today:
            latest = [e for e in after["raw_events"] if e["action"] == common.CHECKIN][-1]
            expect(date_part(latest["date"]) == body["checkin_at"], f"history date {latest['date']!r} != {body['checkin_at']!r}")


# ===================================================================== scenarios
SCENARIOS = []


def scenario(sid, title, requirements, risks):
    def wrap(fn):
        SCENARIOS.append({"id": sid, "title": title, "requirements": requirements, "risks": risks, "fn": fn})
        return fn
    return wrap


def checkout_body(ctx, student=None, **extra):
    return {"checkout_to_type": "user", "assigned_user": student or ctx.fx.student_one, **extra}


@scenario("S-CO-01", "Checkout assigns the student and marks the laptop deployed, with one history entry", ["CO-01"], ["R-A2"])
def s_co_01(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    before = ctx.snap(aid)
    ctx.tech.save(f"hardware/{aid}/checkout", checkout_body(ctx))
    after = ctx.snap(aid)
    expect(after["assigned"] == ctx.fx.student_one, "student not stored")
    expect(after["meta"].casefold() == "deployed", "not deployed")
    expect(after["checkouts"] == before["checkouts"] + 1 and after["out"] == before["out"] + 1, "not exactly one checkout recorded")


@scenario("S-CO-02a", "Expected return date is persisted exactly", ["CO-02"], ["R-A8"])
def s_co_02a(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    ctx.tech.save(f"hardware/{aid}/checkout", checkout_body(ctx, expected_checkin=ctx.due))
    expect(ctx.snap(aid)["due"] == ctx.due, "supplied date not stored")


@scenario("S-CO-02b", "A checkout without a return date stores none", ["CO-02"], ["R-A8"])
def s_co_02b(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    ctx.tech.save(f"hardware/{aid}/checkout", checkout_body(ctx))
    expect(ctx.snap(aid)["due"] is None, "a due date appeared from nowhere")


def rejected_checkout(ctx, aid, body, label):
    before = ctx.snap(aid)
    status, response = common.raw(ctx.tech, "POST", f"hardware/{aid}/checkout", body)
    expect(classify(status, response) == "rejected", f"{label}: expected rejection, got HTTP {status} {response}")
    ctx.unchanged(before, ctx.snap(aid), label)


@scenario("S-CO-03a", "A laptop that needs repair cannot be checked out", ["CO-03"], ["R-A2", "R-A3"])
def s_co_03a(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    ctx.admin.request("PATCH", f"hardware/{aid}", {"status_id": ctx.fx.repair["id"]})
    rejected_checkout(ctx, aid, checkout_body(ctx), "non-deployable status")


@scenario("S-CO-03b", "An archived laptop cannot be checked out", ["CO-03"], ["R-A2"])
def s_co_03b(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    ctx.admin.request("PATCH", f"hardware/{aid}", {"status_id": ctx.archived["id"]})
    rejected_checkout(ctx, aid, checkout_body(ctx), "archived status")


@scenario("S-CO-03c", "A second checkout is rejected and the first loan stays intact", ["CO-03"], ["R-A2", "R-A3"])
def s_co_03c(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    ctx.loan(aid, ctx.fx.student_one, ctx.due)
    rejected_checkout(ctx, aid, checkout_body(ctx, ctx.fx.student_two, expected_checkin=common.due_date(30)), "duplicate checkout")
    expect(ctx.snap(aid)["assigned"] == ctx.fx.student_one, "original borrower lost")


@scenario("S-CO-03d", "A deleted laptop cannot be checked out", ["CO-03"], ["R-A2"])
def s_co_03d(ctx):
    created = ctx.admin.save("hardware", {"asset_tag": "API-DEL-001", "model_id": ctx.fx.model["id"], "status_id": ctx.fx.ready["id"]}) \
        if not ctx.admin.request("GET", "hardware/bytag/API-DEL-001").get("id") else ctx.admin.request("GET", "hardware/bytag/API-DEL-001")
    aid = created["id"]
    ctx.admin.request("DELETE", f"hardware/{aid}")
    status, response = common.raw(ctx.tech, "POST", f"hardware/{aid}/checkout", checkout_body(ctx))
    expect(classify(status, response) == "rejected", f"deleted asset accepted: HTTP {status} {response}")
    rows = common.raw(ctx.admin, "GET", f"hardware/{aid}")[1]
    expect(not (rows or {}).get("assigned_to"), "deleted asset got a borrower")
    ctx.admin.request("POST", f"hardware/{aid}/restore")


@scenario("S-CO-03e", "A checkout to a user id that does not exist is rejected", ["CO-01", "CO-03"], ["R-A8"])
def s_co_03e(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    rejected_checkout(ctx, aid, checkout_body(ctx, 2147483647), "unknown user")


@scenario("S-CI-01", "Check-in clears the assignee and due date and records one return", ["CI-01"], ["R-A5"])
def s_ci_01(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    ctx.loan(aid, due=ctx.due)
    before = ctx.snap(aid)
    ctx.tech.save(f"hardware/{aid}/checkin", {"status_id": ctx.fx.ready["id"]})
    after = ctx.snap(aid)
    expect(after["assigned"] is None and after["due"] is None, "loan fields not cleared")
    expect(after["checkins"] == before["checkins"] + 1 and after["in"] == before["in"] + 1, "not exactly one return recorded")


@scenario("S-CI-02", "A deployable return can be lent again", ["CI-02"], ["R-A2"])
def s_ci_02(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    ctx.loan(aid, ctx.fx.student_one, ctx.due)
    ctx.tech.save(f"hardware/{aid}/checkin", {"status_id": ctx.fx.ready["id"]})
    ctx.loan(aid, ctx.fx.student_two, common.due_date(10))
    after = ctx.snap(aid)
    expect(after["assigned"] == ctx.fx.student_two and after["due"] == common.due_date(10), "re-loan not recorded")


@scenario("S-CI-03", "A return marked for repair stays unavailable and cannot be lent", ["CI-03"], ["R-A2", "R-A3"])
def s_ci_03(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    ctx.loan(aid, due=ctx.due)
    ctx.tech.save(f"hardware/{aid}/checkin", {"status_id": ctx.fx.repair["id"]})
    after = ctx.snap(aid)
    expect(after["status"] == ctx.fx.repair["id"] and after["assigned"] is None, "repair status or release not stored")
    rejected_checkout(ctx, aid, checkout_body(ctx), "checkout after repair return")


@scenario("S-CI-04a", "A repeated empty check-in is rejected without a second return", ["CI-04"], ["R-A5", "R-A3"])
def s_ci_04a(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    ctx.loan(aid, due=ctx.due)
    ctx.tech.save(f"hardware/{aid}/checkin", {"status_id": ctx.fx.ready["id"]})
    before = ctx.snap(aid)
    status, response = common.raw(ctx.tech, "POST", f"hardware/{aid}/checkin", {})
    expect(classify(status, response) == "rejected", f"repeat accepted: {response}")
    ctx.unchanged(before, ctx.snap(aid), "repeated check-in")


@scenario("S-CI-04b", "A repeated check-in with metadata updates the record but records no second return", ["CI-04"], ["R-A5"])
def s_ci_04b(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    ctx.loan(aid, due=ctx.due)
    ctx.tech.save(f"hardware/{aid}/checkin", {"status_id": ctx.fx.ready["id"]})
    before = ctx.snap(aid)
    status, response = common.raw(ctx.tech, "POST", f"hardware/{aid}/checkin", {"name": "SQE metadata update"})
    expect(classify(status, response) == "accepted", f"metadata update refused: {response}")
    after = ctx.snap(aid)
    expect(after["name"] == "SQE metadata update", "metadata not stored")
    expect(after["in"] == before["in"] and after["checkins"] == before["checkins"], "a second return was recorded")


@scenario("S-AUTH-01", "A read-only reviewer cannot check out or check in, and nothing changes", ["CO-03", "CI-03"], ["R-A4"])
def s_auth_01(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    before = ctx.snap(aid)
    status, _ = common.raw(ctx.reviewer, "POST", f"hardware/{aid}/checkout", checkout_body(ctx))
    expect(status == 403, f"reviewer checkout returned HTTP {status}")
    ctx.unchanged(before, ctx.snap(aid), "denied checkout")
    ctx.loan(aid, due=ctx.due)
    loaned = ctx.snap(aid)
    status, _ = common.raw(ctx.reviewer, "POST", f"hardware/{aid}/checkin", {"status_id": ctx.fx.ready["id"]})
    expect(status == 403, f"reviewer check-in returned HTTP {status}")
    ctx.unchanged(loaned, ctx.snap(aid), "denied check-in")


@scenario("S-AUTH-02", "Requests without a token are refused", ["CO-03"], ["R-A4"])
def s_auth_02(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    before = ctx.snap(aid)
    anonymous = common.SnipeApi("not-a-token")
    status, _ = common.raw(anonymous, "POST", f"hardware/{aid}/checkout", checkout_body(ctx))
    expect(status == 401, f"anonymous checkout returned HTTP {status}")
    ctx.unchanged(before, ctx.snap(aid), "anonymous checkout")


@scenario("S-CONC-01", "Two simultaneous checkouts leave exactly one loan and one history entry", ["CO-03"], ["R-A2"])
def s_conc_01(ctx):
    aid = ctx.flow_asset
    ctx.reset(aid)
    before = ctx.snap(aid)

    def attempt(student):
        return common.raw(ctx.tech, "POST", f"hardware/{aid}/checkout", checkout_body(ctx, student))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (ctx.fx.student_one, ctx.fx.student_two)))
    outcomes = sorted(classify(s, b) for s, b in results)
    expect(outcomes == ["accepted", "rejected"], f"expected one winner, got {outcomes}")
    after = ctx.snap(aid)
    expect(after["out"] == before["out"] + 1 and after["checkouts"] == before["checkouts"] + 1, "duplicate checkout recorded")


# ================================================================== orchestration
def load_known():
    return json.loads(KNOWN.read_text(encoding="utf-8")) if KNOWN.exists() else {}


def execute(label, kind, meta, fn, known, results):
    started = time.time()
    entry = {"id": label, "kind": kind, **meta}
    defect = known.get(label)
    reproduced = False
    try:
        observed = fn()
        failure = None
        entry["observed"] = observed
    except ReproducedDefect as error:
        reproduced = bool(defect and error.issue == defect["issue"])
        failure = str(error)
        entry["observed"] = error.observed
    except Failure as error:
        failure = str(error)
    except Exception as error:  # an unexpected crash is a failure too, never silently skipped
        failure = f"{type(error).__name__}: {error}\n{traceback.format_exc(limit=3)}"
    entry["seconds"] = round(time.time() - started, 3)
    if failure is None:
        entry["status"] = "XPASS" if defect else "PASS"
        if defect:
            entry["message"] = f"Known defect {defect['issue']} no longer reproduces; remove it from known-defects.json"
    else:
        entry["status"] = "XFAIL" if reproduced else "FAIL"
        entry["message"] = failure
        if reproduced:
            entry["defect"] = defect
    results.append(entry)
    print(f"{entry['status']:5} {label}" + (f"  -- {failure.splitlines()[0][:150]}" if failure else ""))


def write_reports(results, case_doc):
    OUT.mkdir(parents=True, exist_ok=True)
    totals = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "XFAIL", "FAIL", "XPASS")}
    common.write_json(OUT / "results.json", {"specVersion": case_doc["specVersion"], "generatedCases": case_doc["count"],
                                            "totals": totals, "results": results})
    lines = [f'<?xml version="1.0" encoding="UTF-8"?>', f'<testsuite name="usman-api" tests="{len(results)}" '
             f'failures="{totals["FAIL"] + totals["XPASS"]}" skipped="{totals["XFAIL"]}">']
    for r in results:
        lines.append(f'  <testcase classname={quoteattr(r["kind"])} name={quoteattr(r["id"])} time="{r["seconds"]}">')
        if r["status"] in ("FAIL", "XPASS"):
            lines.append(f'    <failure message={quoteattr(r.get("message", "")[:400])}/>')
        elif r["status"] == "XFAIL":
            lines.append(f'    <skipped message={quoteattr("known defect " + r["defect"]["issue"] + ": " + r["message"][:300])}/>')
        lines.append("  </testcase>")
    lines.append("</testsuite>")
    (OUT / "junit.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = [f"# API test summary\n", f"Spec version {case_doc['specVersion']}; {len(results)} tests: " +
               ", ".join(f"{v} {k}" for k, v in totals.items()) + "\n",
               "| Test | Kind | Requirements | Risks | Status |", "| --- | --- | --- | --- | --- |"]
    for r in results:
        summary.append(f"| {r['id']} | {r['kind']} | {', '.join(r.get('requirements', []))} | {', '.join(r.get('risks', []))} | {r['status']} |")
    (OUT / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--admin-id", type=int, required=True)
    parser.add_argument("--spec", default=str(SPEC))
    parser.add_argument("--only", help="run only test ids containing this text")
    args = parser.parse_args()

    spec = generate_cases.load(args.spec)
    cases = generate_cases.generate(spec)
    case_doc = {"specVersion": spec["info"]["version"], "count": len(cases)}
    known = load_known()
    results = []
    try:
        with ExitStack() as stack:
            admin = stack.enter_context(common.local_api(args.admin_id, "SQE usman admin"))
            fx = common.Fixtures(admin)
            tech = stack.enter_context(common.local_api(fx.technician, "SQE usman technician"))
            reviewer = stack.enter_context(common.local_api(fx.reviewer, "SQE usman reviewer"))
            ctx = Context(admin, tech, reviewer, fx)
            for item in SCENARIOS:
                if args.only and args.only not in item["id"]:
                    continue
                meta = {"requirements": item["requirements"], "risks": item["risks"], "title": item["title"]}
                execute(item["id"], "scenario", meta, lambda f=item["fn"]: f(ctx), known, results)
            for case in cases:
                if args.only and args.only not in case["id"]:
                    continue
                meta = {"requirements": case["requirements"], "risks": case["risks"], "title": case["partition"],
                        "technique": case["technique"], "field": case["field"]}
                execute(case["id"], "generated", meta,
                        lambda c=case: run_generated(ctx, c, known.get(c["id"])), known, results)
            for asset_id in (ctx.gen_asset, ctx.flow_asset, *sorted(ctx.boundary_assets)):
                ctx.reset(asset_id)
    except Exception as error:
        print(f"SETUP ERROR: {error}", file=sys.stderr)
        traceback.print_exc()
        return 2
    totals = write_reports(results, case_doc)
    print("\n" + ", ".join(f"{v} {k}" for k, v in totals.items()) + f"  (reports in {OUT})")
    return 1 if totals["FAIL"] or totals["XPASS"] else 0


if __name__ == "__main__":
    sys.exit(main())
