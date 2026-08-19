# 403 Handling Upgrade

- Auto mode now falls back from Requests to Playwright when static access returns HTTP 403.
- Playwright uses its genuine Chromium user-agent instead of a custom scraper user-agent.
- Browser HTTP status is checked explicitly.
- CAPTCHA, human-verification, access-denied and browser-check pages are detected and stopped.
- The scraper does not bypass login, CAPTCHA, paywalls, anti-bot controls or permissions.
