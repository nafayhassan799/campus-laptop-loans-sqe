"""Seed synthetic laptop-loan fixtures and exercise the local Snipe-IT REST API."""

import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
import json
from pathlib import Path
import secrets
import subprocess
from urllib.parse import urlencode


ROOT = Path(__file__).resolve().parents[2]
ASSET_TAG = "LAB-001"
LOAN_FIELDS = ("name", "assigned_to", "expected_checkin", "status", "checkin_counter", "checkout_counter")


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


class SnipeApi:
    def __init__(self, token, port=8000):
        self.token = token
        self.port = port

    def request(self, method, path, body=None, expected=200):
        data = None if body is None else json.dumps(body).encode()
        connection = HTTPConnection("127.0.0.1", self.port, timeout=15)
        try:
            connection.request(method, f"/api/v1/{path}", body=data, headers={
                "Host": f"localhost:{self.port}",
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            })
            with connection.getresponse() as response:
                status, raw = response.status, response.read()
        finally:
            connection.close()
        check(status == expected, f"{method} {path}: expected HTTP {expected}, got {status}")
        return json.loads(raw) if raw else None

    def save(self, path, body):
        result = self.request("POST", path, body)
        check(result.get("status") == "success", f"POST {path}: {result.get('messages')}")
        return result["payload"]

    def fixture(self, resource, field, value, **attributes):
        query = urlencode({"search": value, "limit": 50})
        rows = self.request("GET", f"{resource}?{query}")["rows"]
        matches = [row for row in rows if row.get(field) == value]
        check(len(matches) <= 1, f"Duplicate fixture {resource}/{value}")
        return matches[0] if matches else self.save(resource, {field: value, **attributes})


@contextmanager
def local_api(user_id):
    result = subprocess.run([
        "docker", "compose", "-p", "sqe-campus-laptops", "exec", "-T", "-u", "docker", "app",
        "php", "artisan", "snipeit:make-api-key", f"--user_id={user_id}",
        "--name=SQE local smoke test", "--key-only",
    ], cwd=ROOT, capture_output=True, text=True, check=False, timeout=30)
    tokens = [line.strip() for line in result.stdout.splitlines() if line.startswith("eyJ")]
    check(result.returncode == 0 and len(tokens) == 1, f"Could not create a local API token for user {user_id}")
    api = SnipeApi(tokens[0])
    try:
        yield api
    finally:
        api.request("POST", "logout", expected=204)


def user_fixture(admin, username, name, permissions=None):
    attributes = {"first_name": name, "last_name": "SQE", "activated": permissions is not None}
    if permissions is not None:
        password = secrets.token_urlsafe(24) + "Aa1!"
        attributes.update(permissions=permissions, password=password, password_confirmation=password)
    return admin.fixture("users", "username", username, **attributes)["id"]


def check_unchanged(before, after):
    for field in LOAN_FIELDS:
        check(after[field] == before[field], f"Rejected or repeated action changed {field}")


def restore_fixture(tech, path, starting_asset, borrowers):
    current = tech.request("GET", path)
    assignee = current["assigned_to"]
    if assignee and assignee["id"] not in borrowers:
        raise RuntimeError(f"Cannot reset {ASSET_TAG}: it has a borrower outside the SQE fixtures")

    changes = {}
    if current["status"]["id"] != starting_asset["status"]["id"]:
        changes["status_id"] = starting_asset["status"]["id"]
    if current["name"] != starting_asset["name"]:
        if starting_asset["name"]:
            changes["name"] = starting_asset["name"]
        else:
            changes["clear_name"] = "1"
    if assignee or changes:
        tech.save(f"{path}/checkin", changes)


def check_checkout_name_boundary(tech, path, checkout):
    spec = json.loads(Path(__file__).with_name("hardware-loans.openapi.json").read_text(encoding="utf-8"))
    operation = spec["paths"]["/hardware/{asset_id}/checkout"]["post"]
    fields = operation["requestBody"]["content"]["application/json"]["schema"]["properties"]
    max_length = fields["name"]["maxLength"]
    before = tech.request("GET", path)
    for length in (max_length - 1, max_length, max_length + 1):
        name = "L" * length
        result = tech.request("POST", f"{path}/checkout", {**checkout, "name": name})
        observed = tech.request("GET", path)
        if length > max_length:
            check(result["status"] == "error", f"Accepted a checkout name of {length} characters")
            check_unchanged(before, observed)
        else:
            check(result["status"] == "success", f"Rejected a checkout name of {length} characters")
            check(observed["name"] == name, f"Checkout did not persist the full {length}-character name")
            check(observed["assigned_to"]["id"] == checkout["assigned_user"], "Checkout did not persist the borrower")
            restore_fixture(tech, path, before, (checkout["assigned_user"],))
            before = tech.request("GET", path)
            check(before["assigned_to"] is None and before["expected_checkin"] is None, "Boundary case left a loan active")
        print(f"PASS checkout asset name length {length}")


def run(admin, sessions):
    view_permission = {"assets.view": 1}
    technician_id = user_fixture(admin, "sqe_lab_technician", "Technician", {
        **view_permission, "assets.checkout": 1, "assets.checkin": 1,
    })
    reviewer_id = user_fixture(admin, "sqe_read_only", "Reviewer", view_permission)
    student_one = user_fixture(admin, "sqe_student_sara", "Sara")
    student_two = user_fixture(admin, "sqe_student_ali", "Ali")
    category = admin.fixture("categories", "name", "SQE Laptops", category_type="asset")
    model = admin.fixture("models", "name", "SQE Campus Laptop", category_id=category["id"])
    status = admin.fixture("statuslabels", "name", "SQE Ready to Deploy", type="deployable")
    repair = admin.fixture("statuslabels", "name", "SQE Needs Repair", type="undeployable")
    asset = admin.fixture("hardware", "asset_tag", ASSET_TAG, model_id=model["id"], status_id=status["id"])
    path = f"hardware/{asset['id']}"
    tech = sessions.enter_context(local_api(technician_id))
    reviewer = sessions.enter_context(local_api(reviewer_id))

    initial = reviewer.request("GET", path)
    check(initial["asset_tag"] == ASSET_TAG and initial["assigned_to"] is None, "Fixture must start unassigned")
    check(initial["status"]["id"] == status["id"], "Fixture must start ready to deploy")
    borrowers = (student_one, student_two)
    sessions.callback(restore_fixture, tech, path, initial, borrowers)
    checkout_count = initial["checkout_counter"]
    due = (datetime.now(timezone.utc).date() + timedelta(days=7)).isoformat()
    checkout = {"checkout_to_type": "user", "assigned_user": student_one, "expected_checkin": due}
    checkin = {"status_id": status["id"]}

    reviewer.request("POST", f"{path}/checkout", checkout, expected=403)
    check_unchanged(initial, reviewer.request("GET", path))
    tech.save(f"{path}/checkout", checkout)
    loan = reviewer.request("GET", path)
    check(loan["assigned_to"]["id"] == student_one, "Checkout did not persist the student assignment")
    check(loan["expected_checkin"]["datetime"][:10] == due, "Checkout did not persist the expected return date")
    check(loan["status"]["status_meta"].casefold() == "deployed", "Checked-out asset is not deployed")
    check(loan["checkout_counter"] == checkout_count + 1, "Checkout count did not increment once")

    denied = tech.request("POST", f"{path}/checkout", {**checkout, "assigned_user": student_two})
    check(denied.get("status") == "error", "A second checkout was not rejected")
    reviewer.request("POST", f"{path}/checkin", checkin, expected=403)
    check_unchanged(loan, reviewer.request("GET", path))

    tech.save(f"{path}/checkin", checkin)
    returned = reviewer.request("GET", path)
    check(returned["assigned_to"] is None and returned["expected_checkin"] is None, "Check-in did not clear the loan")
    check(returned["status"]["id"] == status["id"], "Check-in did not restore the deployable status")
    check(returned["checkin_counter"] == loan["checkin_counter"] + 1, "Check-in count did not increment once")

    repeated = tech.request("POST", f"{path}/checkin", {})
    check(repeated.get("status") == "error", "A check-in without an active loan was not rejected")
    check_unchanged(returned, reviewer.request("GET", path))
    tech.save(f"{path}/checkin", checkin)
    check_unchanged(returned, reviewer.request("GET", path))

    tech.save(f"{path}/checkout", {**checkout, "assigned_user": student_two})
    second_loan = reviewer.request("GET", path)
    check(second_loan["assigned_to"]["id"] == student_two, "Returned laptop could not be lent again")
    check(second_loan["checkout_counter"] == checkout_count + 2, "Unexpected checkout count after re-loan")
    tech.save(f"{path}/checkin", {"status_id": repair["id"]})
    in_repair = reviewer.request("GET", path)
    check(in_repair["assigned_to"] is None and in_repair["expected_checkin"] is None, "Repair return retained the loan")
    check(in_repair["status"]["id"] == repair["id"], "Check-in did not persist the repair status")
    rejected = tech.request("POST", f"{path}/checkout", checkout)
    check(rejected.get("status") == "error", "Checkout was allowed while the laptop needed repair")
    check_unchanged(in_repair, reviewer.request("GET", path))

    restore_fixture(tech, path, initial, borrowers)
    check_checkout_name_boundary(tech, path, checkout)
    reset = reviewer.request("GET", path)
    check(reset["assigned_to"] is None and reset["expected_checkin"] is None, "Fixture did not return to its starting state")
    check(reset["status"]["id"] == status["id"] and reset["name"] == initial["name"], "Fixture metadata was not reset")
    print(f"PASS {ASSET_TAG}: checkout, denied actions, repeated check-in, repair status, and re-loan")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-id", type=int, required=True, help="ID of the local setup administrator")
    args = parser.parse_args()
    with ExitStack() as sessions:
        admin = sessions.enter_context(local_api(args.admin_id))
        run(admin, sessions)


if __name__ == "__main__":
    main()
