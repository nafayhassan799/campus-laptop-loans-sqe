// k6 script: lab technician opens the laptop checkout form.
//   k6 run -e BASE_URL=http://localhost:8000 -e USERNAME=... -e PASSWORD=... -e ASSET_ID=5 \
//          -e VUS=5 -e HOLD=60 -e P95_MS=1500 -e SUMMARY=out.json tests/team/usman/perf/checkout_form.js
// A login redirect or an error page counts as an unexpected failure, never as a success.
import http from 'k6/http';
import { check, sleep } from 'k6';
import execution from 'k6/execution';
import { Counter, Rate, Trend } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'http://localhost:8000';
const VUS = Number(__ENV.VUS || 1);
const HOLD = Number(__ENV.HOLD || 60);
const WARMUP = Number(__ENV.WARMUP || 5);
const THINK = Number(__ENV.THINK || 1);
const P95 = Number(__ENV.P95_MS || 1000);
const ASSET = __ENV.ASSET_ID;

if (!/^http:\/\/(localhost|127\.0\.0\.1):8000$/.test(BASE)) {
  throw new Error('Run against the loopback SQE application on port 8000.');
}

const formDuration = new Trend('checkout_form_duration', true);
const formRequests = new Counter('checkout_form_requests');
const unexpected = new Rate('unexpected_failure');

export const options = {
  noCookiesReset: true, // keep the technician's session across iterations
  scenarios: {
    technician: {
      executor: 'constant-vus',
      vus: VUS,
      duration: `${WARMUP + HOLD}s`,
      gracefulStop: '15s',
    },
  },
  thresholds: {
    checkout_form_requests: ['count>0'],
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
  signedIn = ok;
}

function atTargetLoad() {
  const elapsed = Date.now() - execution.scenario.startTime;
  return elapsed >= WARMUP * 1000 && elapsed < (WARMUP + HOLD) * 1000;
}

export default function loadCheckoutForm() {
  if (!signedIn) {
    const measuredLogin = atTargetLoad();
    login();
    if (!signedIn) {
      if (measuredLogin) { unexpected.add(1); }
      sleep(THINK);
      return;
    }
  }
  const measured = atTargetLoad();
  const res = http.get(`${BASE}/hardware/${ASSET}/checkout`, { tags: { name: 'checkout_form' } });
  const valid = check(res, {
    'status is 200': (r) => r.status === 200,
    'not redirected to login': (r) => !r.url.includes('/login'),
    'form posts to this laptop checkout': (r) => typeof r.body === 'string'
      && r.body.includes(`/hardware/${ASSET}/checkout`) && r.body.includes('name="assigned_user"'),
  });
  if (measured) {
    formRequests.add(1);
    unexpected.add(!valid);
    if (valid) { formDuration.add(res.timings.duration); }
  }
  if (!valid) {
    console.error(`Checkout form failed at iteration ${__ITER} (HTTP ${res.status})`);
    signedIn = false;
  }
  sleep(THINK);
}

export function handleSummary(data) {
  const m = data.metrics;
  const requests = m.checkout_form_requests ? m.checkout_form_requests.values.count : 0;
  const out = {
    users: VUS, warmupSeconds: WARMUP, holdSeconds: HOLD, p95Limit: P95,
    p95_ms: m.checkout_form_duration ? m.checkout_form_duration.values['p(95)'] : null,
    avg_ms: m.checkout_form_duration ? m.checkout_form_duration.values.avg : null,
    max_ms: m.checkout_form_duration ? m.checkout_form_duration.values.max : null,
    requests,
    requestsPerSecond: requests / HOLD,
    unexpectedFailureRate: m.unexpected_failure ? m.unexpected_failure.values.rate : 0,
    unexpectedFailures: m.unexpected_failure ? m.unexpected_failure.values.passes : 0,
    thresholdsPassed: Object.values(m).every((x) => !x.thresholds || Object.values(x.thresholds).every((t) => t.ok)),
    thresholds: Object.fromEntries(Object.entries(m).filter(([, v]) => v.thresholds).map(([k, v]) => [k, v.thresholds])),
  };
  return { [__ENV.SUMMARY || 'k6-summary.json']: JSON.stringify(out, null, 2), stdout: JSON.stringify(out, null, 2) + '\n' };
}
