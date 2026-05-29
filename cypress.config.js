const { defineConfig } = require("cypress");

module.exports = defineConfig({
  defaultCommandTimeout: 30000,
  pageLoadTimeout: 30000,
  responseTimeout: 60000,  // dispatch_campaign can take time
  video: true,
  videosFolder: "../../cypressVideos/",
  viewportHeight: 960,
  viewportWidth: 1400,
  retries: {
    runMode: 1,
    openMode: 0,
  },
  e2e: {
    testIsolation: false,
    baseUrl: "http://tapbuddy.local:8000",
    specPattern: [
      "cypress/e2e/**/*.js",
    ],
    setupNodeEvents(on, config) {
      on('task', {
        hmac({ secret, body }) {
          const crypto = require('crypto');
          return crypto.createHmac('sha256', secret).update(body).digest('hex');
        }
      });
      return config;
    },
  },
  env: {
    adminPassword: "admin@123",
  },
});
