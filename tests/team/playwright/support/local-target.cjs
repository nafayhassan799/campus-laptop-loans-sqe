// Guard used before any fixture credential leaves this machine (owner: Rafay Imran).
//
// The seeded passwords and API tokens are only valid for the disposable local test app.
// Every entry point (Playwright config, the shared fixtures, Lighthouse) calls these checks first,
// so a mistyped SQE_BASE_URL, a stale fixtures.json from another instance, or a non-local proxy
// stops the run before a sign-in or an Authorization header is sent.
const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]']);

/** Throws unless `value` is an http(s) URL on a loopback host. Returns the parsed URL. */
function assertLocalUrl(value, what) {
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`${what} "${value}" is not a valid URL; refusing to use the test credentials.`);
  }
  if (!['http:', 'https:'].includes(url.protocol) || !LOOPBACK_HOSTS.has(url.hostname)) {
    throw new Error(`${what} "${value}" is not the local test app (loopback http only); refusing to use the test credentials.`);
  }
  return url;
}

/** The app under test and the instance the fixtures were seeded against must be the same local origin. */
function assertLocalTarget(baseUrl, fixturesBaseUrl) {
  const app = assertLocalUrl(baseUrl, 'Base URL');
  const seeded = assertLocalUrl(fixturesBaseUrl, 'fixtures.json baseUrl');
  if (app.origin !== seeded.origin) {
    throw new Error(`Base URL ${app.origin} differs from the instance the fixtures were seeded for (${seeded.origin}). Re-run seed.py for this app.`);
  }
  return app.origin;
}

const defaultBaseUrl = () => process.env.SQE_BASE_URL || 'http://localhost:8000';

module.exports = { assertLocalUrl, assertLocalTarget, defaultBaseUrl, LOOPBACK_HOSTS };
