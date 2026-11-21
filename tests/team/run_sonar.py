"""Scan the local PHP application and save SonarQube measures and gate results."""

import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import subprocess
from tempfile import gettempdir
import time
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "output" / "nafay-quality"
SONAR = "sqe-sonar-local"
PROJECT = "campus-laptop-loans"
SERVER = "sonarqube@sha256:7b2296713a92b8ea0dd7a083a25faadc59376c9a1e6daf2744a89711c54ea1ba"
SCANNER = "sonarsource/sonar-scanner-cli@sha256:6e6eca4d552695a98fb7dab84f0c1bd0885ebbfe272654d1552e24bd7f452d51"
METRICS = (
    "ncloc,complexity,cognitive_complexity,duplicated_lines_density,bugs,vulnerabilities,"
    "code_smells,coverage,line_coverage,branch_coverage,sqale_index,sqale_rating,"
    "reliability_rating,security_rating,security_hotspots,blocker_violations"
)


def docker(*args, **options):
    return subprocess.run(["docker", *args], check=True, **options)


def api(path, password=None, query=None, data=None):
    headers = {}
    if password is not None:
        headers["Authorization"] = "Basic " + base64.b64encode(f"admin:{password}".encode()).decode()
    url = "http://127.0.0.1:9000/api/" + path
    if query:
        url += "?" + urlencode(query)
    body = urlencode(data).encode() if data is not None else None
    request = Request(url, data=body, headers=headers)
    with build_opener(ProxyHandler({})).open(request, timeout=10) as response:
        payload = response.read()
        return json.loads(payload) if payload else None


def start():
    network = subprocess.run(["docker", "network", "inspect", SONAR], capture_output=True)
    if network.returncode:
        docker("network", "create", SONAR)
    result = subprocess.run(["docker", "inspect", SONAR, "--format", "{{.State.Running}}"],
                            capture_output=True, text=True)
    if result.returncode:
        docker("run", "-d", "--name", SONAR, "--network", SONAR, "-p", "127.0.0.1:9000:9000",
               "-e", "SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true", SERVER)
    elif result.stdout.strip() != "true":
        docker("start", SONAR)
    for _ in range(90):
        try:
            status = api("system/status")
            if status["status"] == "UP":
                return status
        except OSError:
            pass
        time.sleep(2)
    raise RuntimeError("The dedicated SonarQube container did not become ready")


def authenticate(server_id):
    file = Path(gettempdir()) / f"sqe-sonar-{server_id}.key"
    if file.exists():
        password = file.read_text(encoding="utf-8").strip()
        if api("authentication/validate", password)["valid"]:
            return password
    password = secrets.token_urlsafe(32)
    api("users/change_password", "admin", data={
        "login": "admin", "previousPassword": "admin", "password": password,
    })
    fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(password)
    return password


def scan(password):
    coverage = EVIDENCE / "clover.xml"
    if not coverage.is_file():
        raise RuntimeError("Run the PHP coverage suite before scanning SonarQube")
    report = ET.parse(coverage)
    for node in report.iter("file"):
        if node.attrib["name"].startswith("/var/www/html/"):
            node.attrib["name"] = node.attrib["name"].replace("/var/www/html/", "/usr/src/", 1)
    report.write(EVIDENCE / "sonar-clover.xml", encoding="utf-8", xml_declaration=True)
    token_name = f"sqe-scan-{secrets.token_hex(5)}"
    token = api("user_tokens/generate", password, data={"name": token_name})["token"]
    try:
        return subprocess.run([
            "docker", "run", "--rm", "--network", SONAR, "-e", "SONAR_TOKEN",
            "--mount", f"type=bind,source={ROOT},target=/usr/src",
            SCANNER, f"-Dsonar.host.url=http://{SONAR}:9000",
            f"-Dsonar.projectKey={PROJECT}", "-Dsonar.sources=app",
            "-Dsonar.tests=tests/team/WhiteBox", "-Dsonar.scm.disabled=true",
            "-Dsonar.working.directory=output/nafay-quality/sonar-work",
            "-Dsonar.php.coverage.reportPaths=output/nafay-quality/sonar-clover.xml",
            "-Dsonar.php.tests.reportPath=output/nafay-quality/phpunit-junit.xml",
            "-Dsonar.qualitygate.wait=true", "-Dsonar.qualitygate.timeout=180",
        ], env=os.environ | {"SONAR_TOKEN": token}, check=False).returncode
    finally:
        api("user_tokens/revoke", password, data={"name": token_name})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-gate", action="store_true", help="Fail if the SonarQube quality gate fails")
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    status = start()
    password = authenticate(status["id"])
    result = scan(password)
    measures = api("measures/component", password, query={"component": PROJECT, "metricKeys": METRICS})
    gate = api("qualitygates/project_status", password, query={"projectKey": PROJECT})
    evidence = {"server_version": status["version"], "measures": measures["component"]["measures"],
                "quality_gate": gate["projectStatus"]}
    (EVIDENCE / "sonar-metrics.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"SonarQube {status['version']} quality gate: {evidence['quality_gate']['status']}")
    if result and (args.require_gate or evidence["quality_gate"]["status"] == "OK"):
        raise SystemExit(result)


if __name__ == "__main__":
    main()
