"""Shared helpers for Muhammad Usman's API, performance and recovery work.

Reuses SnipeApi, fixture seeding and the unchanged-state check from the team's
tests/team/smoke_checkout.py. Adds three things the smoke test does not have:

* token minting that works with Docker (default, same command as the smoke test)
  or without it: set SQE_ARTISAN to e.g. "php artisan" for a native install;
* a database command (SQE_DB_CMD) for the fault-injection and settings fixtures;
* a loan-history reader built on the REST activity report.

Environment
  SQE_ARTISAN  command that runs artisan. Default: docker compose ... exec app php artisan
  SQE_DB_CMD   command that opens a SQL shell on the Snipe-IT database. Default for
               Docker: docker compose ... exec -T db mysql -uroot -p<MYSQL_ROOT_PASSWORD> snipeit
               Native example: "mariadb -uroot snipeit"
"""

from contextlib import contextmanager
from datetime import date, timedelta
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

TEAM = Path(__file__).resolve().parents[2]
ROOT = TEAM.parents[1]
sys.path.insert(0, str(TEAM))
import smoke_checkout as smoke  # noqa: E402  (reuse, do not copy)

SnipeApi, check, user_fixture = smoke.SnipeApi, smoke.check, smoke.user_fixture
OUTPUT = ROOT / "output" / "usman"

DOCKER_PROJECT = ["docker", "compose", "-p", "sqe-campus-laptops"]


def artisan_command():
    custom = os.environ.get("SQE_ARTISAN")
    if custom:
        return shlex.split(custom)
    return DOCKER_PROJECT + ["exec", "-T", "-u", "docker", "app", "php", "artisan"]


def db_command():
    custom = os.environ.get("SQE_DB_CMD")
    if custom:
        return shlex.split(custom)
    password = ""
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("MYSQL_ROOT_PASSWORD="):
                password = line.split("=", 1)[1].strip()
    return DOCKER_PROJECT + ["exec", "-T", "db", "mysql", "-uroot", f"-p{password}", "snipeit"]


def sql(statement, fetch=False):
    """Run one SQL statement through the configured database shell."""
    result = subprocess.run(db_command() + ["-N", "-B", "-e", statement], cwd=ROOT, capture_output=True,
                            text=True, timeout=60)
    check(result.returncode == 0, f"SQL failed: {result.stderr.strip()[:300]}")
    if fetch:
        return [line.split("\t") for line in result.stdout.splitlines() if line]
    return None


@contextmanager
def local_api(user_id, name="SQE usman api"):
    result = subprocess.run(artisan_command() + [
        "snipeit:make-api-key", f"--user_id={user_id}", f"--name={name}", "--key-only",
    ], cwd=ROOT, capture_output=True, text=True, check=False, timeout=60)
    tokens = [line.strip() for line in result.stdout.splitlines() if line.startswith("eyJ")]
    check(result.returncode == 0 and len(tokens) == 1, f"Could not create a local API token for user {user_id}")
    api = SnipeApi(tokens[0])
    try:
        yield api
    finally:
        try:
            api.request("POST", "logout", expected=204)
        except RuntimeError:
            pass


def raw(api, method, path, body=None):
    """Send a request and return (http_status, parsed_json_or_None) without asserting the status."""
    from http.client import HTTPConnection
    data = None if body is None else json.dumps(body).encode()
    connection = HTTPConnection("127.0.0.1", 8000, timeout=30)
    try:
        connection.request(method, f"/api/v1/{path}", body=data, headers={
            "Host": "localhost:8000", "Authorization": f"Bearer {api.token}", "Accept": "application/json",
            "Content-Type": "application/json",
        })
        with connection.getresponse() as response:
            status, payload = response.status, response.read()
    finally:
        connection.close()
    try:
        return status, json.loads(payload) if payload else None
    except ValueError:
        return status, {"_unparsed": payload[:200].decode("utf-8", "replace")}


def history(admin, asset_id):
    """Every checkout / checkin / update event for one asset, oldest first (all pages, so long histories are not cut off)."""
    rows, offset, page_size = [], 0, 200
    while True:
        status, body = raw(admin, "GET", f"reports/activity?item_type=asset&item_id={asset_id}&limit={page_size}&offset={offset}&sort=id&order=asc")
        check(status == 200, f"Activity report returned HTTP {status}")
        batch = body.get("rows", [])
        rows.extend(batch)
        offset += len(batch)
        if not batch or offset >= body.get("total", 0):
            break
    return [{"id": r["id"], "action": r["action_type"], "target": (r.get("target") or {}).get("id"),
             "date": (r.get("action_date") or {}).get("datetime") if isinstance(r.get("action_date"), dict) else r.get("action_date")}
            for r in rows if (r.get("item") or {}).get("id") == asset_id]


CHECKOUT, CHECKIN = "checkout", "checkin from"


def count_actions(events, *actions):
    return sum(1 for e in events if e["action"] in actions)


def due_date(days=7):
    return (date.today() + timedelta(days=days)).isoformat()


class Fixtures:
    """Synthetic users, statuses and per-purpose laptops. Each purpose has its own asset."""

    def __init__(self, admin):
        self.admin = admin
        view = {"assets.view": 1}
        self.technician = user_fixture(admin, "sqe_lab_technician", "Technician",
                                       {**view, "assets.checkout": 1, "assets.checkin": 1})
        self.reviewer = user_fixture(admin, "sqe_read_only", "Reviewer", view)
        self.student_one = user_fixture(admin, "sqe_student_sara", "Sara")
        self.student_two = user_fixture(admin, "sqe_student_ali", "Ali")
        category = admin.fixture("categories", "name", "SQE Laptops", category_type="asset")
        self.model = admin.fixture("models", "name", "SQE Campus Laptop", category_id=category["id"])
        self.ready = admin.fixture("statuslabels", "name", "SQE Ready to Deploy", type="deployable")
        self.repair = admin.fixture("statuslabels", "name", "SQE Needs Repair", type="undeployable")
        self.location = admin.fixture("locations", "name", "SQE Return Desk")
        self.location_two = admin.fixture("locations", "name", "SQE Library Counter")

    def asset(self, tag):
        found = self.admin.fixture("hardware", "asset_tag", tag, model_id=self.model["id"], status_id=self.ready["id"])
        return found["id"]


def reset_asset(tech, asset_id, ready_status_id):
    """Return an asset to deployable and unassigned with no name, whatever state a test left it in."""
    current = tech.request("GET", f"hardware/{asset_id}")
    if current["assigned_to"]:
        tech.request("POST", f"hardware/{asset_id}/checkin", {"status_id": ready_status_id, "clear_name": "1"})
    else:
        tech.request("POST", f"hardware/{asset_id}/checkin", {"status_id": ready_status_id, "clear_name": "1"})
    after = tech.request("GET", f"hardware/{asset_id}")
    check(after["assigned_to"] is None and after["status"]["id"] == ready_status_id,
          f"Could not reset asset {asset_id}")
    return after


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
