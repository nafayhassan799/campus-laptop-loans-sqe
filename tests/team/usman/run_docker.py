"""Run Usman's checks in a fresh, loopback-only Docker Compose project."""

import argparse
import base64
import os
from pathlib import Path
import secrets
import subprocess
import sys
from tempfile import TemporaryDirectory

from run_all import DEFAULT, HERE, PY, ROOT, select_stages

PORT = 18001


def run_lab(stages):
    project = f"sqe-usman-{secrets.token_hex(6)}"
    settings = {
        "APP_VERSION": "v8.8.4",
        "APP_PORT": f"127.0.0.1:{PORT}",
        "APP_URL": f"http://localhost:{PORT}",
        "APP_KEY": "base64:" + base64.b64encode(secrets.token_bytes(32)).decode(),
        "DB_DATABASE": "snipeit",
        "DB_USERNAME": "snipeit",
        "DB_PASSWORD": secrets.token_hex(18),
        "MYSQL_ROOT_PASSWORD": secrets.token_hex(18),
        "MAIL_MAILER": "log",
        "MAIL_FROM_ADDR": "lab@example.test",
        "MAIL_REPLYTO_ADDR": "lab@example.test",
        "API_THROTTLE_PER_MINUTE": "100000",
    }
    template = (ROOT / ".env.docker").read_text(encoding="utf-8").splitlines()
    with TemporaryDirectory(prefix="sqe-usman-") as directory:
        temp = Path(directory)
        env_file = temp / "lab.env"
        lines = [line for line in template if line.partition("=")[0] not in settings]
        lines.extend(f"{key}={value}" for key, value in settings.items())
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        env_file.chmod(0o600)
        override = temp / "compose.yml"
        override.write_text("services:\n  app:\n    env_file: !override\n      - ${SQE_USMAN_ENV_FILE}\n",
                            encoding="utf-8")
        compose = [
            "docker", "compose", "-p", project, "--env-file", str(env_file),
            "-f", "docker-compose.yml", "-f", "tests/team/compose.migrations.yml",
            "-f", "tests/team/compose.app-changes.yml", "-f", str(override),
        ]
        compose_env = os.environ | settings | {"SQE_USMAN_ENV_FILE": env_file.as_posix()}
        print(f"Starting {project} on http://localhost:{PORT}", flush=True)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::add-mask::{settings['MYSQL_ROOT_PASSWORD']}", flush=True)
        try:
            subprocess.run(compose + ["up", "-d", "--wait", "--wait-timeout", "150"],
                           cwd=ROOT, env=compose_env, check=True)
            app = subprocess.check_output(compose + ["ps", "-q", "app"], cwd=ROOT, env=compose_env, text=True).strip()
            database = subprocess.check_output(compose + ["ps", "-q", "db"], cwd=ROOT, env=compose_env, text=True).strip()
            if not app or not database:
                raise RuntimeError("The disposable app and database containers must both be running.")
            subprocess.run(PY + [str(HERE.parent / "initialize_local.py"), "--port", str(PORT)],
                           cwd=ROOT, check=True)
            runner_env = os.environ | {
                "SQE_LOCAL_PORT": str(PORT),
                "SQE_REQUIRE_BOUNDARY_FIXTURES": "1",
                "SQE_BROWSER_DATA_FILE": str(temp / "fixtures.json"),
                "SQE_ARTISAN": f"docker exec -i -u docker {app} php artisan",
                "SQE_DB_CMD": f"docker exec -i {database} mariadb -uroot -p{settings['MYSQL_ROOT_PASSWORD']} snipeit",
                "SQE_DB_STOP_CMD": f"docker stop {database}",
                "SQE_DB_START_CMD": f"docker start {database}",
            }
            result = subprocess.run(
                PY + [str(HERE / "run_all.py"), "--admin-id", "1", "--stages", ",".join(stages)],
                cwd=ROOT, env=runner_env,
            )
        finally:
            subprocess.run(compose + ["down", "--volumes"], cwd=ROOT, env=compose_env, check=True)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stages", default=",".join(DEFAULT))
    try:
        stages = select_stages(parser.parse_args().stages)
    except ValueError as error:
        parser.error(str(error))
    if "browser" in stages or "perf" in stages:
        stages = select_stages(",".join([*stages, "fixtures"]))
    return run_lab(stages)


if __name__ == "__main__":
    sys.exit(main())
