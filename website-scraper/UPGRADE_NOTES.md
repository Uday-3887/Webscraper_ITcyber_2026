# Universal Auto Extract Upgrade

This version adds URL-only, best-effort extraction.

## What changed

- Added **Universal Auto Extract** as the default preset.
- Added automatic detection for:
  - HTML tables
  - JSON-LD / schema.org records
  - Repeated product, article, card and list structures
  - Visible links
  - Page summary fallback
- Added confidence scoring and dataset type reporting in Preview.
- Auto Detect now retries low-confidence static pages with Playwright.
- Added automatic Next-page link detection.
- Job names are generated from the URL when left blank.
- CSV, JSON and Excel exports still work from the result page.
- Removed the pandas dependency. Excel files are generated directly with openpyxl, so NumPy is no longer required.

## Important limitation

No scraper can reliably understand every website because markup differs and some sites block automation. Universal Auto Extract is best-effort. Use Preview and switch to Custom selectors when the automatically selected dataset is not the one required. Authentication, CAPTCHA, paywalls and access controls are not bypassed.
