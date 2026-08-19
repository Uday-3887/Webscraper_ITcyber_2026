from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urljoin

from scraper.auto_extractor import detect_next_url, extract_auto_data
from scraper.selector_parser import deduplicate_records, extract_contact_information, extract_records
from scraper.static_scraper import ScrapeError, ScrapeResult
from scraper.url_validator import is_safe_browser_request, validate_url


def scrape_dynamic(
    payload: dict[str, Any],
    limits: dict[str, Any],
    *,
    preview: bool = False,
    should_stop: Callable[[], bool] | None = None,
    progress: Callable[[int, int, str], None] | None = None,
) -> ScrapeResult:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ScrapeError('Playwright is not installed. Run: python -m pip install playwright') from exc

    settings = payload.get('settings', {})
    pagination = payload.get('pagination', {})
    max_pages = 1 if preview else min(int(settings.get('max_pages', 1)), limits['max_pages'])
    max_records = 10 if preview else limits['max_records']
    browser_timeout = min(int(settings.get('browser_timeout', 60000)), limits['browser_timeout'])
    delay_ms = int(max(float(settings.get('request_delay', 1)), limits['min_delay']) * 1000)
    preset = payload.get('preset', 'universal')
    headless = bool(settings.get('headless', limits.get('headless', True)))

    start_url = validate_url(payload['website_url']).url
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    visited: list[str] = []
    page_count = 0
    confidence_values: list[float] = []
    metadata: dict[str, Any] = {}

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=headless, timeout=browser_timeout)
            except PlaywrightError as exc:
                raise ScrapeError(
                    'Chromium could not launch. Run: python -m playwright install chromium'
                ) from exc

            # Keep Playwright's genuine browser user-agent and browser defaults.
            # A custom bot user-agent causes some otherwise public pages to reject the request.
            context = browser.new_context(
                ignore_https_errors=False,
                viewport={'width': 1366, 'height': 768},
                locale='en-US',
            )
            page = context.new_page()
            page.set_default_timeout(browser_timeout)

            def guard(route):
                if is_safe_browser_request(route.request.url):
                    route.continue_()
                else:
                    route.abort('blockedbyclient')

            page.route('**/*', guard)

            def navigate(url: str) -> None:
                validate_url(url)
                try:
                    response = page.goto(url, wait_until='domcontentloaded', timeout=browser_timeout)
                except PlaywrightTimeoutError as exc:
                    raise ScrapeError('Dynamic page navigation timed out.') from exc
                validate_url(page.url)
                if response is not None and response.status >= 400:
                    if response.status == 403:
                        raise ScrapeError(
                            'The public page also returned HTTP 403 in a real browser. '
                            'This site does not permit this scraper to access the page.'
                        )
                    if response.status == 429:
                        raise ScrapeError('The website rate-limited the browser request with HTTP 429.')
                    raise ScrapeError(f'The browser received HTTP {response.status}.')

                title = (page.title() or '').lower()
                body_sample = (page.locator('body').inner_text(timeout=5000) or '')[:4000].lower()
                challenge_terms = (
                    'verify you are human', 'captcha', 'access denied',
                    'checking your browser', 'attention required',
                )
                if any(term in title or term in body_sample for term in challenge_terms):
                    raise ScrapeError(
                        'The website displayed a CAPTCHA or access-verification page. '
                        'The scraper will not bypass it; use an authorized API or obtain permission.'
                    )
                wait_selector = str(settings.get('wait_for_selector', '')).strip()
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=browser_timeout)
                    except PlaywrightTimeoutError as exc:
                        raise ScrapeError(f'Wait selector was not found: {wait_selector}') from exc

            navigate(start_url)
            mode = pagination.get('mode', 'auto' if preset == 'universal' else 'none')

            # Universal mode performs a small safe scroll so lazy-loaded public cards/images
            # become part of the rendered DOM. It does not bypass access controls.
            if preset == 'universal' and mode not in {'load_more', 'infinite'}:
                scrolls = 1 if preview else min(3, limits['max_scroll_count'])
                for _ in range(scrolls):
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    page.wait_for_timeout(min(delay_ms, 1500))

            if mode == 'load_more' and not preview:
                selector = pagination.get('load_more_selector', '')
                max_clicks = min(int(pagination.get('max_clicks', 10)), limits['max_load_more_clicks'])
                previous_count = -1
                for click_number in range(max_clicks):
                    if should_stop and should_stop():
                        break
                    locator = page.locator(selector).first if selector else None
                    if not locator or locator.count() == 0 or not locator.is_visible():
                        break
                    locator.click()
                    page.wait_for_timeout(delay_ms)
                    container_selector = payload.get('container_selector') or 'body > *'
                    current_count = page.locator(container_selector).count()
                    if current_count == previous_count:
                        break
                    previous_count = current_count
                    if progress:
                        progress(1, current_count, f'Load More click {click_number + 1}')
            elif mode == 'infinite' and not preview:
                max_scrolls = min(int(pagination.get('max_scrolls', 10)), limits['max_scroll_count'])
                previous_height = 0
                unchanged = 0
                for scroll_number in range(max_scrolls):
                    if should_stop and should_stop():
                        break
                    height = page.evaluate('document.body.scrollHeight')
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    page.wait_for_timeout(delay_ms)
                    if height == previous_height:
                        unchanged += 1
                    else:
                        unchanged = 0
                    previous_height = height
                    if progress:
                        progress(1, len(records), f'Infinite scroll {scroll_number + 1}')
                    if unchanged >= 2:
                        break

            for page_number in range(1, max_pages + 1):
                if should_stop and should_stop():
                    break
                page_count += 1
                if page.url not in visited:
                    visited.append(page.url)
                if progress:
                    progress(page_number, len(records), f'Parsing dynamic page {page_number}')

                html = page.content()
                if preset == 'contact':
                    page_records = extract_contact_information(html, page.url)
                    page_warnings: list[str] = []
                    confidence_values.append(0.9 if page_records else 0.0)
                    metadata.setdefault('dataset_type', 'contact-information')
                elif preset == 'universal':
                    auto_result = extract_auto_data(html, page.url, max_records=max_records - len(records))
                    page_records = auto_result.records
                    page_warnings = auto_result.warnings
                    confidence_values.append(auto_result.confidence)
                    metadata['dataset_type'] = auto_result.dataset_type
                    metadata['auto_details'] = auto_result.details
                else:
                    page_records, page_warnings, matched = extract_records(
                        html, page.url, payload.get('container_selector', ''),
                        payload.get('fields', []), max_records=max_records - len(records)
                    )
                    confidence_values.append(1.0 if page_records else 0.0)
                    metadata['matched_containers'] = matched
                    metadata.setdefault('dataset_type', 'custom-selectors')

                records.extend(page_records)
                records = deduplicate_records(records)[:max_records]
                warnings.extend(page_warnings)

                if preview or len(records) >= max_records or mode in {'none', 'load_more', 'infinite'}:
                    break

                next_url: str | None = None
                if mode == 'auto':
                    next_url = detect_next_url(html, page.url)
                    if not next_url or next_url == 'Not Available' or next_url in visited:
                        break
                    navigate(next_url)
                elif mode == 'next':
                    selector = pagination.get('next_selector', '')
                    locator = page.locator(selector).first if selector else None
                    if not locator or locator.count() == 0:
                        break
                    href = locator.get_attribute('href')
                    if href:
                        next_url = urljoin(page.url, href)
                        if next_url in visited:
                            break
                        navigate(next_url)
                    else:
                        locator.click()
                        page.wait_for_load_state('domcontentloaded')
                elif mode == 'url':
                    pattern = pagination.get('url_pattern', '')
                    start_page = int(pagination.get('start_page', 1))
                    if not pattern or '{page}' not in pattern:
                        break
                    navigate(pattern.format(page=start_page + page_number))
                else:
                    break
                page.wait_for_timeout(delay_ms)

            context.close()
            browser.close()

    except ScrapeError:
        raise
    except PlaywrightTimeoutError as exc:
        raise ScrapeError('Playwright operation timed out.') from exc
    except Exception as exc:
        raise ScrapeError(f'Dynamic scraping failed: {exc}') from exc

    confidence = min(confidence_values) if confidence_values else 0.0
    return ScrapeResult(
        records=deduplicate_records(records), pages_scraped=page_count,
        mode_used='dynamic', warnings=sorted(set(warnings)), visited_urls=visited,
        confidence=confidence, metadata=metadata,
    )
