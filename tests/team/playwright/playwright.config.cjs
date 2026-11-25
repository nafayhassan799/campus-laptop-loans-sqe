// Shared team Playwright configuration (owner: Rafay Imran).
//
// One Chromium setup, one seeded fixture file and one report for every member's
// browser use cases. Each member keeps their specs in their own folder and gets a
// project of the same name, so `--project=<owner>` runs only their tests while a
// plain `npx playwright test` runs the combined suite for CI.
//
// Environment:
//   SQE_BASE_URL     app under test (default http://localhost:8000, local synthetic instance only)
//   SQE_CHROME_PATH  a Chromium binary when Playwright's own download is not installed
//   SQE_ZAP_PROXY    e.g. http://127.0.0.1:8090 to route the normal browser traffic through
//                    OWASP ZAP for the passive scan (never used by the API suites)
const { defineConfig } = require('@playwright/test');
const path = require('node:path');

const output = path.resolve(__dirname, '../../../output/playwright');
const zap = process.env.SQE_ZAP_PROXY;

module.exports = defineConfig({
  testDir: './',
  // Tests change shared global state only through their own laptops, but the
  // flash messages and sessions are simplest to reason about one at a time.
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [
    ['list'],
    ['junit', { outputFile: path.join(output, 'junit.xml') }],
    ['json', { outputFile: path.join(output, 'results.json') }],
    ['html', { outputFolder: path.join(output, 'html'), open: 'never' }],
  ],
  outputDir: path.join(output, 'runs'),
  use: {
    baseURL: process.env.SQE_BASE_URL || 'http://localhost:8000',
    browserName: 'chromium',
    screenshot: 'on',
    trace: 'retain-on-failure',
    ignoreHTTPSErrors: Boolean(zap),
    proxy: zap ? { server: zap, bypass: '' } : undefined,
    launchOptions: {
      executablePath: process.env.SQE_CHROME_PATH || undefined,
      // Chromium never proxies loopback traffic unless told to; ZAP needs to see it.
      args: zap ? ['--proxy-bypass-list=<-loopback>'] : [],
    },
  },
  projects: [
    // Signs each role in once and stores the session under output/ (git-ignored).
    { name: 'setup', testMatch: /auth\.setup\.cjs/ },
    { name: 'rafay', testDir: './rafay', testMatch: /.*\.spec\.cjs/, testIgnore: /a11y\//, dependencies: ['setup'] },
    { name: 'a11y', testDir: './rafay/a11y', testMatch: /.*\.spec\.cjs/, dependencies: ['setup'] },
    // Nafay and Usman: add { name: 'nafay', testDir: './nafay', ... } when the specs move here.
  ],
});
