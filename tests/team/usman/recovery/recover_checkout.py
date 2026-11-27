"""Controlled failure-and-retry test for the state-changing checkout write.

    SQE_ARTISAN="php artisan" SQE_DB_CMD="mariadb -uroot snipeit" \
    SQE_DB_STOP_CMD="mysqladmin -uroot shutdown" \
    SQE_DB_START_CMD="bash -c 'nohup mysqld_safe --user=mysql >/tmp/sqe-mysqld.log 2>&1 &'" \
    python -B tests/team/usman/recovery/recover_checkout.py --admin-id 1 [--mode history-write|db-outage|both]

Two faults, each on its own dedicated laptop (RECOV-001 / RECOV-002) in a disposable local database:

history-write  A BEFORE INSERT trigger on action_logs rejects the 'checkout' history row of the fixture
               laptop. Snipe-IT writes the asset row first and the history row second, inside one transaction,
               so this fails the dependency AFTER the assignment was written. Expected: the transaction rolls
               back; no partial assignment, status change, counter increase or history row remains.
db-outage      The database process is stopped before the request. Expected: the request fails and, after
               the database is back, the record is unchanged.

For each fault the script then restores the dependency, retries the identical request and asserts one
successful assignment, one checkout counter increment and exactly one checkout history entry, and finally
repeats the request to show a retry cannot create a duplicate. Exit code 0 only when every assertion holds.
Raw output is written to output/usman/recovery/.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
import common  # noqa: E402

OUT = common.OUTPUT / "recovery"
TRIGGER = "sqe_fail_checkout_history"
LOG = []


def log(message):
    stamp = f"[{time.strftime('%H:%M:%S')}] {message}"
    LOG.append(stamp)
    print(stamp, flush=True)


def need(condition, message):
    if not condition:
        raise AssertionError(message)
    log(f"ASSERT OK: {message}")


def snap(admin, asset_id):
    a = admin.request("GET", f"hardware/{asset_id}")
    events = common.history(admin, asset_id)
    return {"assigned": (a["assigned_to"] or {}).get("id"), "status": a["status"]["id"], "meta": a["status"].get("status_meta"),
            "due": (a["expected_checkin"] or {}).get("datetime", "")[:10] or None, "out": a["checkout_counter"],
            "last_checkout": (a["last_checkout"] or {}).get("datetime"), "events": [e["id"] for e in events],
            "checkouts": common.count_actions(events, common.CHECKOUT)}


def db_row(asset_id):
    row = common.sql(f"select ifnull(assigned_to,'NULL'), status_id, checkout_counter, ifnull(last_checkout,'NULL'), "
                     f"(select count(*) from action_logs where item_id={asset_id} and item_type like '%Asset' and action_type='checkout') "
                     f"from assets where id={asset_id}", fetch=True)[0]
    return {"assigned_to": row[0], "status_id": row[1], "checkout_counter": row[2], "last_checkout": row[3], "checkout_log_rows": row[4]}


def wait_for_database(admin, seconds=60):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            common.sql("select 1", fetch=True)
            status, _ = common.raw(admin, "GET", "hardware/1")
            if status < 500:
                return
        except Exception:
            pass
        time.sleep(1)
    raise AssertionError("database did not come back")


def run_fault(mode, admin, tech, fx, asset_id):
    log(f"=== fault: {mode} on asset {asset_id} ===")
    common.reset_asset(tech, asset_id, fx.ready["id"])
    before = snap(admin, asset_id)
    before_db = db_row(asset_id)
    log(f"before: {json.dumps(before_db)}")
    body = {"checkout_to_type": "user", "assigned_user": fx.student_one, "expected_checkin": common.due_date(7)}
    evidence = {"mode": mode, "asset": asset_id, "request": body, "before": before_db}
    fault_removed = False

    def restore():
        nonlocal fault_removed
        if fault_removed:
            return
        if mode == "history-write":
            common.sql(f"drop trigger if exists {TRIGGER}")
        else:
            subprocess.run(shlex.split(START_CMD), capture_output=True, text=True, timeout=60, check=True)
            wait_for_database(admin)
        fault_removed = True
        log("dependency restored")

    try:
        if mode == "history-write":
            common.sql(f"drop trigger if exists {TRIGGER}")
            common.sql(f"delimiter //\ncreate trigger {TRIGGER} before insert on action_logs for each row begin "
                       f"if new.item_id={asset_id} and new.action_type='checkout' then "
                       f"signal sqlstate '45000' set message_text='SQE injected history-store failure'; end if; end//\ndelimiter ;")
            log("fault injected: action_logs rejects the checkout history row (asset row is written first)")
        else:
            subprocess.run(shlex.split(STOP_CMD), capture_output=True, text=True, timeout=60, check=True)
            time.sleep(2)
            log("fault injected: database stopped")

        try:
            status, response = common.raw(tech, "POST", f"hardware/{asset_id}/checkout", body)
        except TimeoutError:
            if mode != "db-outage":
                raise
            evidence["failedAttempt"] = {"http": None, "transport": "timeout"}
            log("attempt during confirmed database outage: HTTP connection timed out")
        else:
            evidence["failedAttempt"] = {"http": status, "body": response}
            log(f"attempt during fault: HTTP {status} {json.dumps(response)[:120]}")
            failed = not (status == 200 and isinstance(response, dict) and response.get("status") == "success")
            need(failed, "the checkout request did not report success while the dependency was failing")

        if mode == "history-write":
            during = snap(admin, asset_id)
            during_db = db_row(asset_id)
            evidence["duringFault"] = during_db
            need(during["assigned"] is None and during_db["assigned_to"] == "NULL", "no partial assignment remains (assigned_to is empty)")
            need(during["status"] == before["status"], "status label did not change")
            need(during["out"] == before["out"] and during_db["checkout_counter"] == before_db["checkout_counter"], "checkout counter did not change")
            need(during["last_checkout"] == before["last_checkout"], "last_checkout did not change")
            need(during["events"] == before["events"] and during_db["checkout_log_rows"] == before_db["checkout_log_rows"], "no history row was created")
        restore()

        after_fault = snap(admin, asset_id)
        need(after_fault == before and db_row(asset_id) == before_db,
             "record and checkout history are unchanged after the dependency is restored")

        status, response = common.raw(tech, "POST", f"hardware/{asset_id}/checkout", body)
        evidence["retry"] = {"http": status, "body": response}
        log(f"retry: HTTP {status} {json.dumps(response)[:160]}")
        need(status == 200 and response.get("status") == "success", "the retried checkout succeeded")
        done = snap(admin, asset_id)
        done_db = db_row(asset_id)
        evidence["afterRetry"] = done_db
        need(done["assigned"] == fx.student_one, "exactly one assignment: the student now holds the laptop")
        need(done["meta"].casefold() == "deployed" and done["due"] == body["expected_checkin"], "status is deployed and the due date was stored")
        need(done["out"] == before["out"] + 1 and int(done_db["checkout_counter"]) == int(before_db["checkout_counter"]) + 1, "checkout counter increased by exactly one")
        need(done["checkouts"] == before["checkouts"] + 1 and int(done_db["checkout_log_rows"]) == int(before_db["checkout_log_rows"]) + 1, "exactly one checkout history entry was added")

        status, response = common.raw(tech, "POST", f"hardware/{asset_id}/checkout", body)
        again = snap(admin, asset_id)
        evidence["secondRetry"] = {"http": status, "body": response}
        need(response.get("status") == "error" and again["events"] == done["events"] and again["out"] == done["out"],
             "a further retry is rejected and adds no duplicate history or counter increase")
        evidence["result"] = "PASS"
    except AssertionError as error:
        evidence["result"] = f"FAIL: {error}"
        log(f"FAIL: {error}")
    finally:
        restore()
        try:
            common.reset_asset(tech, asset_id, fx.ready["id"])
        except Exception as error:  # cleanup problems must not hide the test result
            log(f"cleanup warning: {error}")
    evidence["log"] = list(LOG)
    return evidence


def main():
    global STOP_CMD, START_CMD
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--admin-id", type=int, required=True)
    parser.add_argument("--mode", choices=("history-write", "db-outage", "both"), default="both")
    args = parser.parse_args()
    import os
    STOP_CMD = os.environ.get("SQE_DB_STOP_CMD", "docker compose -p sqe-campus-laptops stop db")
    START_CMD = os.environ.get("SQE_DB_START_CMD", "docker compose -p sqe-campus-laptops start db")
    modes = ["history-write", "db-outage"] if args.mode == "both" else [args.mode]
    results = []
    with common.local_api(args.admin_id, "SQE recovery admin") as admin:
        fx = common.Fixtures(admin)
        with common.local_api(fx.technician, "SQE recovery technician") as tech:
            for index, mode in enumerate(modes):
                results.append(run_fault(mode, admin, tech, fx, fx.asset(f"RECOV-00{index + 1}")))
    common.write_json(OUT / "recovery-results.json", results)
    (OUT / "recovery-log.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    ok = all(r["result"] == "PASS" for r in results)
    print("\nRESULT:", ", ".join(f"{r['mode']}={r['result']}" for r in results))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
