"""Seed the shared synthetic fixtures for the team Playwright suite.

    python -B tests/team/playwright/seed.py --admin-id 1

Creates (or reuses) the lab technician and read-only reviewer accounts with fresh
local-only passwords, the two seeded students, the status labels the browser use
cases need, one laptop model and one dedicated laptop per browser test, so tests
that change a loan never share a record. Writes everything the specs need to
output/playwright/fixtures.json (git-ignored, mode 600). It holds temporary API
tokens and generated passwords: never commit it.

Token creation runs `php artisan` in the repository (native stack). For the
Docker stack set SQE_ARTISAN="docker compose -p sqe-campus-laptops exec -T -u docker app php artisan".
"""

import argparse
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "output" / "playwright"
HOST, PORT = "127.0.0.1", 8000

# One laptop per test that changes a loan. Owners add their own tags here.
ASSET_TAGS = [
    # Rafay UC-R1: keyboard checkout
    "RAF-CO-MAIN", "RAF-CO-ALT1", "RAF-CO-ALT2", "RAF-CO-EXC1", "RAF-CO-EXC2",
    # Rafay UC-R2: repair return
    "RAF-CI-MAIN", "RAF-CI-ALT1", "RAF-CI-ALT2", "RAF-CI-EXC1", "RAF-CI-EXC2",
    # Rafay access matrix and accessibility scans
    "RAF-AC-01", "RAF-AC-02", "RAF-AC-03", "RAF-AC-04", "RAF-AC-05", "RAF-AC-06",
    "RAF-A11Y-CO", "RAF-A11Y-CI",
]


class Api:
    def __init__(self, token):
        self.token = token

    def request(self, method, path, body=None):
        connection = HTTPConnection(HOST, PORT, timeout=30)
        try:
            connection.request(method, f"/api/v1/{path}", body=None if body is None else json.dumps(body), headers={
                "Host": f"localhost:{PORT}", "Authorization": f"Bearer {self.token}",
                "Accept": "application/json", "Content-Type": "application/json",
            })
            with connection.getresponse() as response:
                status, raw = response.status, response.read()
        finally:
            connection.close()
        if status >= 400:
            raise RuntimeError(f"{method} {path}: HTTP {status} {raw[:300]!r}")
        return json.loads(raw) if raw else None

    def save(self, method, path, body):
        result = self.request(method, path, body)
        if result.get("status") != "success":
            raise RuntimeError(f"{method} {path}: {result.get('messages')}")
        return result["payload"]

    def find(self, resource, field, value):
        rows = self.request("GET", f"{resource}?{urlencode({'search': value, 'limit': 50})}")["rows"]
        matches = [row for row in rows if row.get(field) == value]
        if len(matches) > 1:
            raise RuntimeError(f"Duplicate fixture {resource}/{value}")
        return matches[0] if matches else None

    def fixture(self, resource, field, value, **attributes):
        return self.find(resource, field, value) or self.save("POST", resource, {field: value, **attributes})


def artisan():
    configured = os.environ.get("SQE_ARTISAN")
    return shlex.split(configured) if configured else ["php", "artisan"]


def make_token(user_id):
    result = subprocess.run(artisan() + ["snipeit:make-api-key", f"--user_id={user_id}",
                                         "--name=SQE shared playwright", "--key-only"],
                            cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    tokens = [line.strip() for line in result.stdout.splitlines() if line.startswith("eyJ")]
    if result.returncode != 0 or len(tokens) != 1:
        raise RuntimeError(f"Could not create a local API token for user {user_id}: {result.stderr[-300:]}")
    return tokens[0]


def account(admin, username, first_name, permissions):
    """Create or update a browser login with exactly the given permissions and a fresh password."""
    password = secrets.token_urlsafe(18) + "Aa1!"
    body = {"first_name": first_name, "last_name": "SQE", "activated": True, "permissions": permissions,
            "password": password, "password_confirmation": password}
    existing = admin.find("users", "username", username)
    user = admin.save("PATCH", f"users/{existing['id']}", body) if existing else \
        admin.save("POST", "users", {"username": username, **body})
    return {"id": user["id"], "username": username, "password": password,
            "name": f"{first_name} SQE"}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--admin-id", type=int, required=True)
    args = parser.parse_args()
    admin = Api(make_token(args.admin_id))

    students = []
    for first in ("Sara", "Ali"):
        username = f"sqe_student_{first.lower()}"
        user = admin.fixture("users", "username", username, first_name=first, last_name="SQE", activated=False)
        students.append({"id": user["id"], "username": username, "name": f"{first} SQE"})

    technician = account(admin, "sqe_lab_technician", "Lab Technician",
                         {"assets.view": "1", "assets.checkout": "1", "assets.checkin": "1"})
    reviewer = account(admin, "sqe_read_only", "Reviewer", {"assets.view": "1"})

    statuses = {
        "ready": ("SQE Ready to Deploy", "deployable"),
        "repair": ("SQE Needs Repair", "undeployable"),
        "pending": ("SQE Pending Assessment", "pending"),
    }
    labels = {key: {"id": admin.fixture("statuslabels", "name", name, type=kind)["id"], "name": name}
              for key, (name, kind) in statuses.items()}
    category = admin.fixture("categories", "name", "SQE Laptops", category_type="asset")
    model = admin.fixture("models", "name", "SQE Campus Laptop", category_id=category["id"])

    assets = {}
    for tag in ASSET_TAGS:
        found = admin.request("GET", f"hardware/bytag/{tag}")
        if not (found and found.get("id")):
            found = admin.save("POST", "hardware", {"asset_tag": tag, "model_id": model["id"],
                                                    "status_id": labels["ready"]["id"]})
        assets[tag] = found["id"]

    technician["token"] = make_token(technician["id"])
    data = {
        "baseUrl": f"http://localhost:{PORT}",
        "admin": {"id": args.admin_id, "token": admin.token},
        "technician": technician,
        "reviewer": reviewer,
        "students": students,
        "status": labels,
        "model": {"id": model["id"], "name": "SQE Campus Laptop"},
        "assets": assets,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / "fixtures.json"
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    target.chmod(0o600)
    print(f"Seeded {len(assets)} laptops, technician {technician['username']}, "
          f"reviewer {reviewer['username']}; wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
