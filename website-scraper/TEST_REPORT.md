# ScrapeFlow Universal — Validation Report

Validation date: 2026-08-05

## Passed checks

- Python compilation for all project modules
- JavaScript syntax checks for app, scraper and results scripts
- Jinja parsing for all templates
- Universal HTML-table detection
- Universal repeated-card detection
- Relative link and image URL resolution
- Price detection for repeated product records
- JSON-LD/schema extraction
- Visible-link fallback extraction
- Automatic Next-page URL discovery
- Duplicate record handling
- CSV export
- JSON export
- Excel XLSX export using openpyxl
- URL validation unit files remain included
- Responsive UI templates remain included

## Dependency improvement

`pandas` was removed from the project. As a result, installation no longer needs the large NumPy dependency. Excel export now uses `openpyxl` directly.

## Environment limitation during packaging

The packaging container did not have Flask installed and did not have external package/DNS access. Therefore, the full Flask HTTP test suite and a live external website request could not be executed in this container. All Python modules compiled successfully, core extraction/export logic was executed directly, JavaScript passed syntax checks, and templates parsed successfully.

Run the complete local checks after setup:

```powershell
python -m pytest -q
python app.py
```
