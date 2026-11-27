# Defensive security assessment: laptop checkout and check-in

Owner: Rafay Imran. Date: 2026-11-25. Target: the team's local synthetic Snipe-IT v8.8.4 on `http://localhost:8000`. It ran with `php -S` and MariaDB 10.11, with `APP_ENV=production`, `APP_DEBUG=false` and `ENABLE_CSP=true`.
Scope: passive inspection, source and configuration review, and ordinary application actions with the two test roles. No active scanning, fuzzing or exploit attempts were made.

## 1. Attack surface: routes and data in the two workflows

| Route | Controller | Gate | Reads | Writes |
| --- | --- | --- | --- | --- |
| `GET /hardware/{asset}/checkout` | `Assets\AssetCheckoutController@create` | `authorize('checkout', $asset)`, then `availableForCheckout()` | asset, status labels, users (select2), locations | none |
| `POST /hardware/{assetId}/checkout` | `@store` (`AssetCheckoutRequest`) | validation, availability, then `authorize('checkout')`, then a row lock with a recheck | as above | `assets.assigned_to/assigned_type`, `expected_checkin`, `status_id`, `name`, `location_id`, `requestable`, `checkout_counter`; `action_logs` (checkout); checkout acceptance |
| `GET /hardware/{asset}/checkin/{backto?}` | `Assets\AssetCheckinController@create` | `authorize('checkin')`, then "is assigned" | asset, the last checkout log | none |
| `POST /hardware/{assetId}/checkin/{backto?}` | `@store` (`AssetCheckinRequest`) | "is assigned", then `authorize('checkin')` | as above | clears `assigned_to` and `expected_checkin`; sets `status_id`, `name`, `location_id`, `last_checkin`, `checkin_counter`; `action_logs` (checkin from); deletes pending acceptances |
| `GET /hardware/{asset}` and the History tab (`GET /api/v1/hardware/{asset}/history`) | `AssetsController@show`, `Api\AssetsController@history` | `view` | asset, history | none |
| `POST /api/v1/hardware/{id}/checkout`, `/checkin`, plus `bytag/{tag}/checkout` and `/checkin`, `checkinbytag` | `Api\AssetsController` | Passport token or session, then the same policies | same | same |
| `GET /api/v1/users/selectlist` and `/locations/selectlist` | select2 look-ups | `view` on the list | names and usernames of users | none |

Sensitive data on these paths includes student identity (name, username), the loan relationship, due dates, free-text notes (damage reports), and the session and XSRF cookies. API tokens are personal access tokens (JWTs).

## 2. Two-role access matrix (expected)

| Action | Lab technician (`assets.view/checkout/checkin`) | Read-only reviewer (`assets.view`) | No session |
| --- | --- | --- | --- |
| View laptop record and history | Allowed | Allowed, with no loan actions offered | Sign-in |
| Open the checkout form | Allowed | **Denied (403)** | Sign-in |
| Submit a checkout | Allowed | **Denied (403), nothing saved** | Sign-in |
| Open the check-in form | Allowed | **Denied (403)** | Sign-in |
| Submit a check-in | Allowed | **Denied (403), loan kept** | Sign-in |
| Edit the asset (outside the workflows) | **Denied (403)** | Denied | Sign-in |

Source: `app/Policies/CheckoutablePermissionsPolicy.php` (`checkout()` = `assets.checkout`, `checkin()` = `assets.checkin`) and `SnipePermissionsPolicy::view()` = `assets.view`. The seeded permissions are in `tests/team/playwright/seed.py` and were confirmed in the database (`users.permissions`).

## 3. Observed decisions (Playwright, `rafay/access-matrix.spec.cjs`)

Each check is an ordinary action: a page load, or the same form POST the UI sends, using that role's own session cookie and CSRF token. Persisted state is read back over REST.
Raw output: `evidence/security/access-matrix.json`. Screenshots are in the Playwright report.

| ID | Role | Action | Expected | Observed |
| --- | --- | --- | --- | --- |
| AC-01 | technician | GET checkout form | allowed | HTTP 200, `#checkout_form` visible |
| AC-02 | technician | POST checkout | allowed, saved | HTTP 302; `assigned_to`=Sara, `checkout_counter` +1 |
| AC-03 | technician | POST check-in (repair) | allowed, saved | HTTP 302; `assigned_to`=null, status SQE Needs Repair, `checkin_counter` +1 |
| AC-04 | technician | GET asset edit form | denied | HTTP 403 |
| AC-05 | reviewer | GET laptop record | allowed, read-only | HTTP 200, no checkout or check-in links |
| AC-06 | reviewer | GET checkout form | denied | HTTP 403, no form |
| AC-07 | reviewer | POST checkout | denied, unchanged | HTTP 403; `assigned_to`=null, `checkout_counter` unchanged |
| AC-08 | reviewer | GET check-in form | denied | HTTP 403 |
| AC-09 | reviewer | POST check-in | denied, loan kept | HTTP 403; `assigned_to`=Sara, `checkin_counter` unchanged |
| AC-10 | none | GET checkout form | sign-in | redirected to `/login` |
| AC-11 | technician | POST checkout **without** CSRF token | refused, unchanged | HTTP 302 to the same-origin form with "Your form session has expired. Please try again."; nothing saved |

The same decisions are also covered inside the use cases (UC-R1-EXC2 for the reviewer checkout) and by Nafay's reviewer check-in test.

## 4. Security controls reviewed (observation corroborated by source and configuration)

### C1 Session cookie and session handling

| Attribute | Observed (`Set-Cookie` on `POST /login`, captured by ZAP) | Source / configuration | Assessment |
| --- | --- | --- | --- |
| HttpOnly | `snipeit_session=…; httponly` | `config/session.php` has no `http_only` key, so the Laravel default (`true`) applies | OK |
| SameSite | `samesite=lax` (both cookies) | Laravel default `lax` (no `same_site` key) | OK. It also blocks cross-site POSTs carrying the session |
| Secure | **absent** | `config/session.php:159` `'secure' => env('SECURE_COOKIES', false)`; `.env` `SECURE_COOKIES=false` | Acceptable only on this loopback HTTP instance. **Must be `true` behind HTTPS** (SEC-03) |
| Lifetime | `Max-Age=720000` (200 h ≈ 8.3 days) | `config/session.php:40` `SESSION_LIFETIME` default **12000 minutes**; `EXPIRE_ON_CLOSE=false` | **Finding SEC-04**: lab PCs are shared, so a technician who walks away stays signed in for days |
| Session ID rotation on login | The pre-login and post-login `snipeit_session` values differ (curl check) | `app/Http/Controllers/Auth/LoginController.php:561` `session()->regenerate(true)` | OK (prevents session fixation) |
| XSRF-TOKEN cookie | not HttpOnly | Laravel design: JavaScript reads it to send `X-XSRF-TOKEN` | Accepted (ZAP 10010 is expected here) |

### C2 Role permission checks

* Observed: AC-01…AC-10 above. Reviewer writes return 403 with the asset unchanged, and the technician is denied outside the role.
* Source: both controllers call `$this->authorize('checkout'|'checkin', $asset)` and the policies map to the permission keys above.
* Observation: in both `store()` methods, `authorize()` runs **after** the existence and availability checks (`AssetCheckoutController.php`, `store()`). A user without the permission who posts to an *unavailable* laptop is told "not available" instead of 403. This is not a bypass, because no write happens before `authorize()`, and the reviewer can already see availability. It is noted as hardening item SEC-07: authorize first.

### C3 CSRF protection

* Observed: AC-11. A POST without the token is refused and nothing is saved.
* Source: `app/Http/Middleware/VerifyCsrfToken.php` excludes only `health`. `app/Exceptions/Handler.php:114` turns `TokenMismatchException` into a redirect to `Helper::sameOriginUrl(url()->previous())` with `general.token_expired`, which prevents an open redirect.

### C4 HTTP security headers (observed on application responses)

`X-Frame-Options: DENY`, `frame-ancestors 'none'`, `Referrer-Policy: same-origin` and `X-Content-Type-Options: nosniff` are present, set by `app/Http/Middleware/SecurityHeaders.php`.
The CSP itself is weak; see SEC-01. HSTS is off (`ENABLE_HSTS=false`), which is correct for plain HTTP but must be enabled with HTTPS.

## 5. OWASP ZAP passive scan

ZAP 2.16.1 ran as a daemon with all 57 passive rules and **no active scan**. The browser suite as it stood at the time of the scan (UC-R1, UC-R2 and access matrix AC-01…AC-10: 23 tests plus the 2 sign-in setups) ran through it with `SQE_ZAP_PROXY`.
754 requests were recorded, and the passive scan queue was drained before export.
Raw output: `evidence/zap/` (`zap-passive-report.html` and `.json`, `zap-alerts-raw.json`, `zap-passive-rules.json`).

| ZAP alert (rule) | Risk | Instances | Triage | Finding |
| --- | --- | --- | --- | --- |
| CSP: script-src `unsafe-inline`, `unsafe-eval`; style-src `unsafe-inline`; no fallback for some directives (10055) | Medium | 40 each, every page | **True positive.** Source: `SecurityHeaders.php:84-86` | SEC-01 |
| Vulnerable JS Library: Bootstrap 3.3.4 in `/js/dist/all.js` (10003) | Medium | 1 | **True positive**, see D-02 | SEC-02 |
| Cross-Domain Misconfiguration: `Access-Control-Allow-Origin: *` on `/api/*` (10098) | Medium | 110 | True, low impact: `config/cors.php:18-19` defaults to `*` when `CORS_ALLOWED_ORIGINS` is unset, but `supports_credentials` is `false`, so cookies are not sent and Bearer tokens are not attached automatically | SEC-05 |
| Cookie No HttpOnly Flag: XSRF-TOKEN (10010) | Low | 41 | False positive by design (C1) | n/a |
| X-Content-Type-Options missing (10021) | Low | 14, static `.css`/`.js` only | Test-environment artifact: `php -S` serves static files without passing through Laravel, while application responses do send `nosniff` (C4). The production web server must add the header for static files | SEC-06 (verify on deployment) |
| Big Redirect Detected (10044) | Low | 14 | False positive: Laravel redirect bodies contain only the target URL | n/a |
| Timestamp Disclosure (10096) | Low | 144 | False positive: `X-RateLimit-Reset` header | n/a |
| Suspicious comments; session management / auth request identified; modern web app (10027, 10112, 10111, 10109) | Info | n/a | Informational, no action | n/a |

## 6. Dependency audit

| Tool | Version | Scope checked |
| --- | --- | --- |
| `composer audit --locked` (Packagist security advisories) | Composer 2.8.12 | 248 locked PHP packages in `composer.lock` (list: `evidence/deps/composer-packages.json`) |
| `npm audit --package-lock-only` (GitHub Advisory Database) | npm 10.9.9 | 1,061 front-end packages in the root `package-lock.json` (build tools plus libraries bundled into `public/js/dist`) |
| `npm audit` | npm 10.9.9 | the team Playwright suite (`tests/team/playwright/package-lock.json`): **0 advisories** |
| ZAP rule 10003 (Retire.js data) | ZAP 2.16.1 | JavaScript actually served to the browser |

Raw output: `evidence/deps/`. Both auditors are the open-source tools native to the stack (PHP / Node). OWASP Dependency-Check was not used. Its NVD mirror needs an API key and does not resolve Composer or npm transitive trees as precisely.

Results: composer audit found 1 advisory; npm audit found 51 (2 critical, 21 high, 18 moderate, 10 low). The relevant observations are below. *Shipped* means the code reaches the browser or server at run time; *build-only* means it is only used by Laravel Mix on a developer machine.

| ID | Component and version | Evidence | Shipped? | Likely impact | Recommended correction |
| --- | --- | --- | --- | --- | --- |
| D-01 | `league/csv` 9.28.0 | GHSA-m9j4-54gj-jvf8 (PKSA-kwst-yd6p-pksp): DoS through unbounded buffering in `CharsetConverter`, affects <9.28.1 | Yes (server). The importer uses `League\Csv\Reader`; `CharsetConverter` is **not** referenced in `app/` | Low: the vulnerable class is not on a reachable path. Imports also need admin rights | `composer update league/csv` to ≥ 9.28.1 |
| D-02 | `bootstrap-less` 3.3.8, which embeds **Bootstrap JS 3.3.4** | ZAP 10003 on `/js/dist/all.js`; source map shows `./node_modules/bootstrap-less/js/bootstrap.js`; `resources/assets/js/snipeit.js:16` `require('bootstrap-less')`. CVE-2018-14040/14041/14042 and CVE-2019-8331 (XSS via tooltip/popover/collapse `data-*` options), fixed in 3.4.1. **Not reported by npm audit**, because the package name differs | Yes (all pages) | Medium: needs attacker-controlled `data-*` attributes in rendered HTML. Snipe-IT escapes user content, which lowers the likelihood, but tooltips are used widely | Replace with `require('bootstrap')` (3.4.1 JS already in `package.json`) and rebuild with `npm run prod` |
| D-03 | `bootstrap` 3.4.1 (and `eonasdan-bootstrap-datetimepicker`, which depends on it) | GHSA-vxmc-5x29-h64v, GHSA-q58r-hwc8-rm9j; no fixed 3.x version (Bootstrap 3 is end-of-life) | Yes (CSS, and JS after D-02) | Medium-low: carousel and tooltip `data-*` XSS, same precondition as D-02 | Track as technical debt; plan a move off Bootstrap 3 / AdminLTE 2 |
| D-04 | `xlsx` (SheetJS) 0.18.5, through `tableexport.jquery.plugin` 1.33.0 | GHSA-4r6h-8v6p-xvw6 (prototype pollution when *reading* crafted files), GHSA-5pgg-2g8v-p4x9 (ReDoS); bundled in `/js/dist/bootstrap-table.js` | Yes (list pages) | Low: Snipe-IT uses it only to *export* tables, not to parse uploaded spreadsheets | Use SheetJS ≥ 0.20.2 from the vendor CDN tarball, or drop the xlsx export |
| D-05 | `chart.js` 1.1.1 nested under `admin-lte` | GHSA-h68q-55jf-x68w | **No**: the app bundles its own `chart.js` 2.9.4 (`public/js/dist/Chart.min.js`) | None at run time | Clears when `admin-lte` is upgraded |
| D-06 | Build-only chain: `webpack-dev-server` ≤5.2.7, `express`/`body-parser`/`path-to-regexp`/`qs`, `ws`, `websocket-driver` (critical), `proxy-addr` (critical), `@babel/*`, `minimatch`, `picomatch`, `svgo`, `tmp`, … | `evidence/deps/npm-audit-frontend.json` | No (Laravel Mix tooling) | Developer machines only, and only while `npm run watch/hot` is running (source disclosure through the dev server) | `npm audit fix` where non-breaking; upgrade Laravel Mix/webpack; never run the dev server on a shared network |

## 7. Security findings for triage

| ID | Finding | Severity (proposed) | Linked risk | Proposed fix |
| --- | --- | --- | --- | --- |
| SEC-01 | CSP allows `unsafe-inline` and `unsafe-eval` for scripts, so it does not mitigate XSS. Inline scripts already carry `nonce="{{ csrf_token() }}"`, but the policy does not use nonces. That nonce is also the per-session CSRF token, not a per-response value | Medium | PR-07 | Generate a per-response nonce, add `'nonce-…'` to `script-src` and drop `unsafe-inline`; remove `unsafe-eval` after checking Livewire/Alpine |
| SEC-02 | Bootstrap 3.3.4 JS shipped through `bootstrap-less` (D-02) | Medium | PR-07 | `require('bootstrap')` and rebuild |
| SEC-03 | Session cookie lacks `Secure` (configuration) | Medium on any HTTPS deployment; n/a on loopback | PR-08 | `SECURE_COOKIES=true` and `ENABLE_HSTS=true` with HTTPS |
| SEC-04 | 8.3-day idle session lifetime on shared lab PCs | Medium | PR-08 | `SESSION_LIFETIME=30` (minutes) and `EXPIRE_ON_CLOSE=true` for the lab |
| SEC-05 | `Access-Control-Allow-Origin: *` on the API | Low | PR-07 | Set `CORS_ALLOWED_ORIGINS` to the app origin |
| SEC-06 | `nosniff` missing on static files under `php -S` | Low (verify on Apache/nginx) | PR-07 | Web-server header for `/css`, `/js` |
| SEC-07 | `authorize()` after the availability checks in `store()` | Info / hardening | PR-05 | Authorize first |
| D-01 | `league/csv` DoS advisory | Low | PR-07 | Upgrade |

Verified controls with no finding: role checks on all four workflow routes (AC-01…AC-10), CSRF enforcement (AC-11), session ID rotation on login, HttpOnly and SameSite on the session cookie, clickjacking protection (`X-Frame-Options: DENY`, `frame-ancestors 'none'`), and an open-redirect-safe CSRF error path.
