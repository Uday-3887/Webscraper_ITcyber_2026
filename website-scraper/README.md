# ScrapeFlow — Website Scraper

A complete Flask website scraper with **Universal Auto Extract**. Enter a public URL and the application automatically detects tables, JSON-LD/schema data, repeated product/article cards, lists, links or page content, then exports the detected dataset to CSV, JSON and Excel. Custom CSS selectors remain available for precise extraction.

## HTTP 403 handling

In **Auto Detect** mode, ScrapeFlow now retries a blocked static request once using a normal Playwright Chromium browser. It uses Playwright's genuine browser defaults rather than a custom bot user-agent. If the browser also receives HTTP 403, a CAPTCHA, login wall, or verification challenge, the job stops with a clear message. The project does not bypass access controls; use an official API or obtain authorization for those sites.


## Responsible-use rule

Use this application only for public pages you own or are authorized to scrape. Follow the target site's Terms of Service, robots.txt, privacy rules and applicable law. The application does not implement CAPTCHA bypass, login bypass, anti-bot evasion, proxy rotation, paywall bypass or collection of hidden private data.

## Main features

- Universal Auto Extract: URL-only scraping without CSS selectors
- Automatic HTML table, JSON-LD, repeated-card, link and page-summary detection
- Static, Dynamic and Auto Detect modes
- CSS-selector-based extraction with text, attribute, link, image and HTML modes
- Presets for Universal Auto, products, articles, links, images, headings, contacts and Books to Scrape
- Automatic Next-page link detection
- Next-button, URL-pattern, Load More and infinite-scroll pagination
- Preview first 10 records
- Background jobs with live polling and cancellation
- SQLite jobs, records and reusable configurations
- CSV, JSON and Excel downloads
- URL validation, private-network blocking, redirect checks and Playwright network guard
- robots.txt checker
- Responsive Bootstrap dashboard
- Docker, Render, Railway/VPS-ready structure

## Requirements

- Python 3.10 or newer. Python 3.12 or 3.13 is recommended.
- Windows 10/11, Linux or macOS
- Internet connection for installing packages and the Chromium browser

## Windows installation

Open PowerShell in the project folder:

```powershell
cd "C:\path\to\website-scraper"
py -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

### PowerShell activation error

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

### Missing Python package

Always install into the active virtual environment:

```powershell
python -m pip install -r requirements.txt
```

### Playwright browser missing or Chromium launch error

```powershell
python -m pip install --upgrade playwright
python -m playwright install chromium
python -m playwright install --list
```

If the browser cache is damaged:

```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\ms-playwright"
python -m playwright install chromium
```

### Port 5000 already in use

PowerShell:

```powershell
$env:PORT=5050
python app.py
```

Open `http://127.0.0.1:5050`.

## Fastest use: URL only

1. Open **New Scraper**.
2. Keep **Universal Auto** and **Auto Detect** selected.
3. Paste a public page URL. Job name is generated automatically if left empty.
4. Confirm responsible use.
5. Select **Preview first 10**.
6. Start the job and download CSV, JSON or Excel.

The system chooses the strongest structured dataset found. Preview is important because no universal algorithm can understand every possible website perfectly. Login pages, CAPTCHA, access blocks and private data are not bypassed.

## Selector-controlled test: Books to Scrape

The Books demo preset contains:

```text
URL: https://books.toscrape.com/
Container: article.product_pod
Title: h3 a → attribute title
Price: .price_color → text
Availability: .availability → text
Rating: .star-rating → attribute class
Product URL: h3 a → link href
Next page: li.next a
```

1. Confirm responsible use.
2. Select Preview first 10.
3. Check the table.
4. Start scraping.
5. Watch live status on the result page.
6. Download CSV, JSON or Excel.

## Static versus dynamic mode

**Static** uses Requests and BeautifulSoup. Use it when data appears in View Page Source.

**Dynamic** launches Chromium with Playwright. Use it when JavaScript loads the data, or when the page uses Load More / infinite scrolling.

**Auto Detect** tries static HTML first. For Universal Auto mode, it scores the detected dataset. If the static result is empty or low-confidence, it renders the page with Playwright and keeps the stronger result.

## CSS selector examples

| Target | Selector |
|---|---|
| Class | `.product-card` |
| ID | `#main` |
| Tag with class | `a.product-link` |
| Nested element | `.product-card .price` |
| Attribute present | `a[href]` |
| Multiple heading tags | `h1, h2, h3` |

A container should represent one repeated record. Field selectors are searched inside each container.

## API endpoints

```text
POST   /api/preview
POST   /api/scrape
POST   /api/robots
GET    /api/jobs
GET    /api/jobs/<id>
POST   /api/jobs/<id>/stop
DELETE /api/jobs/<id>
GET    /api/configurations
POST   /api/configurations
GET    /api/configurations/<id>
PUT    /api/configurations/<id>
POST   /api/configurations/<id>/duplicate
DELETE /api/configurations/<id>
GET    /api/export/<job_id>/csv
GET    /api/export/<job_id>/json
GET    /api/export/<job_id>/excel
```

## Folder structure

```text
website-scraper/
├── app.py
├── config.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── render.yaml
├── database/
├── routes/
├── scraper/
├── services/
├── templates/
├── static/
├── exports/
├── logs/
└── tests/
```

## Tests

```powershell
python -m pytest -q
```

The tests cover URL blocking, automatic table/JSON-LD/card detection, automatic pagination discovery, selector extraction, link resolution, duplicate removal, lightweight CSV/JSON/Excel exporters and core Flask routes. Dynamic browser behaviour should also be checked manually because it requires an installed Chromium binary.

## Docker

```powershell
docker compose up --build
```

Open `http://127.0.0.1:5000`.

The Dockerfile uses Microsoft's Playwright Python image, which already contains supported browser dependencies.

## Render

The included `render.yaml` uses the Docker runtime. Create a new Blueprint deployment from the repository. Use persistent storage for `database`, `exports` and `logs` when long-term history is required.

## Railway / VPS

Build with the Dockerfile. Set:

```env
SECRET_KEY=a-long-random-value
PLAYWRIGHT_HEADLESS=true
PORT=8000
```

Start command when not using Docker:

```text
gunicorn --workers 1 --threads 4 --timeout 700 --bind 0.0.0.0:$PORT app:app
```

Use one worker because the included lightweight background-job controller stores cancellation events in process memory. For higher scale, replace background threads with Celery/RQ and Redis.

## Netlify and Vercel note

This is not a static website. Requests, SQLite, background jobs and Playwright require a persistent Python backend. Do not deploy the full application as a normal static Netlify site. Serverless limits can also be unsuitable for browser jobs.

## Security notes

The URL validator blocks unsupported schemes, credentials in URLs, localhost, private IPs, loopback, link-local, reserved and cloud metadata-style hosts. Static redirects are manually revalidated. Playwright network requests are guarded to prevent public pages from requesting local/private resources.

No generic SSRF defense is mathematically perfect in every infrastructure. In production, also use outbound firewall rules, container isolation, DNS controls, per-user rate limits and a strict allowlist where possible.

## Manual testing checklist

- [ ] Valid public URL works
- [ ] Invalid URL shows a friendly message
- [ ] `localhost`, `127.0.0.1` and private IPs are blocked
- [ ] Static preview returns up to 10 records
- [ ] Dynamic Chromium job runs after browser installation
- [ ] Universal Auto detects a table, JSON-LD, repeated cards, links or a page summary
- [ ] Auto Detect retries with Playwright when the static result is empty or low-confidence
- [ ] Incorrect selector returns an empty-results message
- [ ] Next-button pagination stops at the page limit
- [ ] URL-pattern pagination formats `{page}` correctly
- [ ] Load More stops when the button disappears or records stop changing
- [ ] Infinite scroll stops after unchanged page height
- [ ] Stop button changes a running job to stopped
- [ ] CSV, JSON and Excel files download
- [ ] Saved configuration can be run, duplicated and deleted
- [ ] Job deletion removes exported files
- [ ] Tables work on mobile width
- [ ] HTTP 403, 429, timeout and unsupported content errors are friendly

## Known production considerations

Universal extraction is best-effort: websites use different markup and some intentionally block automated access. Preview the result and use Custom selectors when the automatically selected dataset is not the one you need.

This project is a strong single-server implementation. For high-volume production use, add authentication, CSRF protection for browser sessions, Redis-backed job queues, database migrations, PostgreSQL, per-user quotas, audit logs, antivirus scanning for exports, and infrastructure-level egress filtering.

## Secure login and full-site crawling
Default local login is `admin` / `Admin@123`. Change `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env` before deployment.
Enable **Crawl complete website** to discover same-domain pages from sitemap.xml and internal links. The crawler tracks visited URLs, prevents loops, skips binary files, respects configured delays and page/record limits, and records the source page for every row.

No crawler can guarantee every page on every site. Pages hidden behind login, CAPTCHA, access controls, unsupported forms, disconnected URLs, or server blocks are not bypassed. Use an official API or owner-provided export where available.
