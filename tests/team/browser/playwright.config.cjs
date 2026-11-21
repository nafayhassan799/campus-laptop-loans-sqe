const { defineConfig } = require('@playwright/test');
const path = require('node:path');

const output = path.resolve(__dirname, '../../../output/nafay-quality/browser');

module.exports = defineConfig({
  testDir: './',
  workers: 1,
  reporter: [['list'], ['junit', { outputFile: path.join(output, 'junit.xml') }],
    ['html', { outputFolder: path.join(output, 'html'), open: 'never' }]],
  outputDir: path.join(output, 'runs'),
  use: {
    baseURL: 'http://localhost:8000',
    browserName: 'chromium',
    screenshot: 'only-on-failure',
  },
});
