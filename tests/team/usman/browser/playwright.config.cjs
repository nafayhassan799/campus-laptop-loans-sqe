// Playwright settings for Muhammad Usman's two browser use cases.
// SQE_CHROME_PATH points at an installed Chrome when Playwright's own download is unavailable.
const { defineConfig } = require('@playwright/test');
const path = require('node:path');

const output = path.resolve(__dirname, '../../../../output/usman/browser');

module.exports = defineConfig({
  testDir: './',
  testMatch: /usman-.*\.spec\.cjs/,
  workers: 1, // one shared database and a toggled global setting: tests must not overlap
  retries: 0,
  timeout: 60_000,
  reporter: [['list'], ['junit', { outputFile: path.join(output, 'junit.xml') }],
    ['html', { outputFolder: path.join(output, 'html'), open: 'never' }]],
  outputDir: path.join(output, 'runs'),
  use: {
    baseURL: 'http://localhost:8000',
    browserName: 'chromium',
    screenshot: 'on',
    trace: 'retain-on-failure',
    launchOptions: {
      executablePath: process.env.SQE_CHROME_PATH || undefined,
      args: ['--no-sandbox'],
    },
  },
});
