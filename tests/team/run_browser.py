"""Seed disposable browser fixtures and run the campus laptop loan use cases."""

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess

from smoke_checkout import local_api


def browser_account(admin, username, first_name, permissions):
    password = secrets.token_urlsafe(24) + "Aa1!"
    admin.save("users", {
        "username": username, "first_name": first_name, "last_name": "Browser SQE",
        "password": password, "password_confirmation": password, "activated": True, "permissions": permissions,
    })
    return {"username": username, "password": password}


def seed(admin, stack_id):
    student = [admin.fixture("users", "username", f"sqe_student_{name.lower()}",
                            first_name=name, last_name="SQE", activated=False)
               for name in ("Sara", "Ali")]
    ready = admin.fixture("statuslabels", "name", "SQE Ready to Deploy", type="deployable")
    other = admin.fixture("statuslabels", "name", "SQE Spare Ready", type="deployable")
    repair = admin.fixture("statuslabels", "name", "SQE Needs Repair", type="undeployable")
    category = admin.fixture("categories", "name", "SQE Laptops", category_type="asset")
    model = admin.fixture("models", "name", "SQE Campus Laptop", category_id=category["id"])
    cases = {}
    for scenario in (
        "checkout-main", "checkout-borrower", "checkout-status", "checkout-loaned", "checkout-repair",
        "return-main", "return-status", "return-note", "return-stale", "return-reviewer",
    ):
        asset = admin.save("hardware", {
            "asset_tag": f"SQE-UI-{stack_id}-{scenario}",
            "model_id": model["id"],
            "status_id": repair["id"] if scenario == "checkout-repair" else ready["id"],
        })
        if scenario.startswith("return-") or scenario == "checkout-loaned":
            admin.save(f"hardware/{asset['id']}/checkout", {
                "checkout_to_type": "user", "assigned_user": student[0]["id"], "expected_checkin": "2090-04-15",
            })
        cases[scenario] = asset["id"]
    return {
        "token": admin.token,
        "cases": cases,
        "students": [{"id": user["id"], "name": f"{name} SQE",
                      "option": f"{name} SQE (sqe_student_{name.lower()})"}
                     for user, name in zip(student, ("Sara", "Ali"))],
        "ready": {"id": ready["id"], "name": "SQE Ready to Deploy"},
        "other": {"id": other["id"], "name": "SQE Spare Ready"},
        "repair_id": repair["id"],
        "technician": browser_account(admin, f"sqe_ui_technician_{stack_id}", "Lab", {
            "assets.view": 1, "assets.checkout": 1, "assets.checkin": 1,
        }),
        "reviewer": browser_account(admin, f"sqe_ui_reviewer_{stack_id}", "Reviewer", {"assets.view": 1}),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-id", type=int, required=True)
    args = parser.parse_args()
    browser_dir = Path(__file__).resolve().with_name("browser")
    with local_api(args.admin_id) as admin:
        fixtures = seed(admin, secrets.token_hex(3))
        env = os.environ | {"SQE_BROWSER_DATA": json.dumps(fixtures)}
        result = subprocess.run(
            ["node", "node_modules/@playwright/test/cli.js", "test"],
            cwd=browser_dir, env=env, check=False,
        )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
