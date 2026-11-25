// k6 script: lab technician opens the laptop checkout form.
//   k6 run -e BASE_URL=http://localhost:8000 -e USERNAME=... -e PASSWORD=... -e ASSET_ID=5 \
//          -e VUS=5 -e HOLD=60 -e P95_MS=1500 -e SUMMARY=out.json tests/team/usman/perf/checkout_form.js
// A login redirect or an error page counts as an unexpected failure, never as a success.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'http://localhost:8000';
const VUS = Number(__ENV.VUS || 1);
const HOLD = Number(__ENV.HOLD || 60);
const THINK = Number(__ENV.THINK || 1);
const P95 = Number(__ENV.P95_MS || 1000);
const ASSET = __ENV.ASSET_ID;

const formDuration = new Trend('checkout_form_duration', true);
const formRequests = new Counter('checkout_form_requests');
const unexpected = new Rate('unexpected_failure');

export const options = {
  noCookiesReset: true, // keep the technician's session across iterations
  scenarios: {
    technician: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: VUS > 1 ? [{ duration: '5s', target: VUS }, { duration: `${HOLD}s`, target: VUS }]
                      : [{ duration: '1s', target: 1 }, { duration: `${HOLD}s`, target: 1 }],
      gracefulRampDown: '0s',
    },
  },
  thresholds: {
    checkout_form_duration: [`p(95)<${P95}`],
    unexpected_failure: ['rate<=' + Number(__ENV.MAX_FAIL || 0)],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'max'],
};

let signedIn = false;

function login() {
  const page = http.get(`${BASE}/login`, { tags: { name: 'login_page' } });
  const token = page.html().find('input[name="_token"]').first().attr('value');
  const res = http.post(`${BASE}/login`, { _token: token, username: __ENV.USERNAME, password: __ENV.PASSWORD },
    { tags: { name: 'login' } });
  const ok = check(res, { 'login left the login page': (r) => r.status === 200 && !r.url.includes('/login') });
  if (!ok) { unexpected.add(1); }
  signedIn = ok;
}

export default function () {
  if (!signedIn) { login(); if (!signedIn) { sleep(THINK); return; } }
  const res = http.get(`${BASE}/hardware/${ASSET}/checkout`, { tags: { name: 'checkout_form' } });
  const valid = check(res, {
    'status is 200': (r) => r.status === 200,
    'not redirected to login': (r) => !r.url.includes('/login'),
    'form posts to this laptop checkout': (r) => r.body.includes(`/hardware/${ASSET}/checkout`) && r.body.includes('name="assigned_user"'),
  });
  formRequests.add(1);
  if (valid) { formDuration.add(res.timings.duration); unexpected.add(0); }
  else { console.error('FAIL iter=' + __ITER + ' status=' + res.status + ' url=' + res.url + ' bodyHasForm=' + res.body.includes('name="assigned_user"')); unexpected.add(1); signedIn = false; }
  sleep(THINK);
}

export function handleSummary(data) {
  const m = data.metrics;
  const out = {
    users: VUS, holdSeconds: HOLD, p95Limit: P95,
    p95_ms: m.checkout_form_duration ? m.checkout_form_duration.values['p(95)'] : null,
    avg_ms: m.checkout_form_duration ? m.checkout_form_duration.values.avg : null,
    max_ms: m.checkout_form_duration ? m.checkout_form_duration.values.max : null,
    requests: m.checkout_form_requests ? m.checkout_form_requests.values.count : 0,
    requestsPerSecond: m.checkout_form_requests ? m.checkout_form_requests.values.rate : 0,
    unexpectedFailureRate: m.unexpected_failure ? m.unexpected_failure.values.rate : 0,
    unexpectedFailures: m.unexpected_failure ? m.unexpected_failure.values.passes : 0,
    thresholdsPassed: Object.values(m).every((x) => !x.thresholds || Object.values(x.thresholds).every((t) => !t.ok === false)),
    thresholds: Object.fromEntries(Object.entries(m).filter(([, v]) => v.thresholds).map(([k, v]) => [k, v.thresholds])),
  };
  return { [__ENV.SUMMARY || 'k6-summary.json']: JSON.stringify(out, null, 2), stdout: JSON.stringify(out, null, 2) + '\n' };
}
