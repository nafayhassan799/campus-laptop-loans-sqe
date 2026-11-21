"""Initialize the disposable local Snipe-IT instance for unattended CI."""

from http.cookiejar import CookieJar
import re
import secrets
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, build_opener


BASE = "http://localhost:8000"


def call(client, path, form=None):
    data = urlencode(form).encode() if form is not None else None
    with client.open(BASE + path, data=data, timeout=20) as response:
        if not response.geturl().startswith(BASE + "/"):
            raise RuntimeError("Setup redirected outside the disposable localhost app")
        return response.geturl(), response.read().decode()


def csrf(html):
    match = re.search(r'name="_token"\s+value="([^"]+)"', html)
    if not match:
        raise RuntimeError("No form token in the local setup page")
    return match.group(1)


def main():
    client = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
    for attempt in range(30):
        try:
            url, setup = call(client, "/setup")
            break
        except (URLError, ConnectionError):
            if attempt == 29:
                raise
            time.sleep(2)
    if not url.endswith("/setup"):
        raise RuntimeError("Expected a fresh CI database. The local setup page is unavailable.")

    call(client, "/setup/migrate", {"_token": csrf(setup)})
    _, form = call(client, "/setup/user")
    password = secrets.token_urlsafe(24) + "Aa1!"
    url, _ = call(client, "/setup/user", {
        "_token": csrf(form),
        "site_name": "Campus Laptop Loans SQE",
        "first_name": "Lab",
        "last_name": "Administrator",
        "username": "sqe_ci_admin",
        "email": "sqe-ci-admin@example.test",
        "password": password,
        "password_confirmation": password,
        "locale": "en-US",
        "default_currency": "USD",
    })
    if url not in (BASE + "/", BASE + "/setup/done"):
        raise RuntimeError("Snipe-IT first-run setup failed")
    print("Initialized a synthetic administrator in the disposable CI database.")


if __name__ == "__main__":
    main()
