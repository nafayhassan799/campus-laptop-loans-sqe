"""Seed the shared synthetic fixtures and write local-only credentials for k6, recovery and Playwright.

    SQE_ARTISAN="php artisan" python -B tests/team/usman/prepare_fixtures.py --admin-id 1

Writes output/usman/fixtures.json (git-ignored). It holds temporary local API tokens and
generated passwords for the synthetic technician and reviewer; never commit it.
Each purpose has its own laptop so API, performance, recovery and browser runs do not collide.
"""
import argparse
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "api"))
import common  # noqa: E402

ASSETS = {"perf": "PERF-001", "recovery": "RECOV-001", "browser": ["BR-CO-%02d" % i for i in range(1, 9)] + ["BR-CI-%02d" % i for i in range(1, 9)]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-id", type=int, required=True)
    args = parser.parse_args()
    with common.local_api(args.admin_id, "SQE usman fixtures") as admin:
        fx = common.Fixtures(admin)
        passwords = {}
        for key, user_id in (("technician", fx.technician), ("reviewer", fx.reviewer)):
            password = secrets.token_urlsafe(18) + "Aa1!"
            admin.request("PATCH", f"users/{user_id}", {"password": password, "password_confirmation": password, "activated": True})
            passwords[key] = password
        names = {}
        for key, user_id in (("technician", fx.technician), ("reviewer", fx.reviewer)):
            names[key] = admin.request("GET", f"users/{user_id}")["username"]
        # long-lived local tokens: a new key per run, deleted with the disposable database
        import subprocess
        def token(uid):
            out = subprocess.run(common.artisan_command() + ["snipeit:make-api-key", f"--user_id={uid}", "--name=SQE usman browser", "--key-only"],
                                 cwd=common.ROOT, capture_output=True, text=True, timeout=60).stdout
            return [l.strip() for l in out.splitlines() if l.startswith("eyJ")][0]
        data = {
            "baseUrl": "http://localhost:8000",
            "admin": {"id": args.admin_id, "token": token(args.admin_id)},
            "technician": {"id": fx.technician, "username": names["technician"], "password": passwords["technician"], "token": token(fx.technician)},
            "reviewer": {"id": fx.reviewer, "username": names["reviewer"], "password": passwords["reviewer"]},
            "students": [{"id": fx.student_one, "username": "sqe_student_sara", "name": "Sara SQE"},
                         {"id": fx.student_two, "username": "sqe_student_ali", "name": "Ali SQE"}],
            "ready": fx.ready, "repair": fx.repair, "location": fx.location, "locationTwo": fx.location_two,
            "model": fx.model,
            "assets": {"perf": fx.asset(ASSETS["perf"]), "recovery": fx.asset(ASSETS["recovery"])},
        }
        # The performance laptop must be deployable and unassigned, or its checkout form redirects and every k6 request fails.
        with common.local_api(fx.technician, "SQE usman reset") as tech:
            for asset_id in data["assets"].values():
                common.reset_asset(tech, asset_id, fx.ready["id"])
        common.write_json(common.OUTPUT / "fixtures.json", data)
        (common.OUTPUT / "fixtures.json").chmod(0o600)
        print("Wrote", common.OUTPUT / "fixtures.json", "- perf asset", data["assets"]["perf"], "recovery asset", data["assets"]["recovery"])


if __name__ == "__main__":
    main()
