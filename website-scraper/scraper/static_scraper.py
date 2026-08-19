from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from scraper.auto_extractor import detect_next_url, extract_auto_data
from scraper.selector_parser import deduplicate_records, extract_contact_information, extract_records
from scraper.url_validator import UnsafeURLError, validate_url


class ScrapeError(RuntimeError):
    pass


@dataclass
class ScrapeResult:
    records: list[dict[str, Any]]
    pages_scraped: int
    mode_used: str
    warnings: list[str] = field(default_factory=list)
    visited_urls: list[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


def _download_html(url: str, timeout: int, max_bytes: int) -> tuple[str, str, int]:
    session = requests.Session()
    current = validate_url(url).url
    headers = {
        'User-Agent': 'ResponsibleWebsiteScraper/2.0 (+local educational tool)',
        'Accept': 'text/html,application/xhtml+xml',
    }

    for _ in range(6):
        try:
            response = session.get(
                current, headers=headers, timeout=timeout, allow_redirects=False, stream=True
            )
        except requests.Timeout as exc:
            raise ScrapeError('The website request timed out.') from exc
        except requests.SSLError as exc:
            raise ScrapeError('SSL certificate validation failed.') from exc
        except requests.RequestException as exc:
            raise ScrapeError(f'The website could not be reached: {exc}') from exc

        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get('Location')
            response.close()
            if not location:
                raise ScrapeError('The website returned an invalid redirect.')
            current = urljoin(current, location)
            try:
                validate_url(current)
            except UnsafeURLError as exc:
                raise ScrapeError(f'Unsafe redirect blocked: {exc}') from exc
            continue

        if response.status_code == 403:
            response.close()
            raise ScrapeError('The website blocked automated access with HTTP 403.')
        if response.status_code == 429:
            response.close()
            raise ScrapeError('The website rate-limited the request with HTTP 429.')
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            code = response.status_code
            response.close()
            raise ScrapeError(f'The website returned HTTP {code}.') from exc

        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
            response.close()
            raise ScrapeError(f'Unsupported content type: {content_type or "unknown"}.')

        body = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                body.extend(chunk)
            if len(body) > max_bytes:
                response.close()
                raise ScrapeError('The response body exceeded the configured size limit.')
        encoding = response.encoding or 'utf-8'
        html = bytes(body).decode(encoding, errors='replace')
        final_url = response.url
        status = response.status_code
        response.close()
        return html, final_url, status

    raise ScrapeError('Too many redirects.')


def scrape_static(
    payload: dict[str, Any],
    limits: dict[str, Any],
    *,
    preview: bool = False,
    should_stop: Callable[[], bool] | None = None,
    progress: Callable[[int, int, str], None] | None = None,
) -> ScrapeResult:
    settings = payload.get('settings', {})
    pagination = payload.get('pagination', {})
    max_pages = 1 if preview else min(int(settings.get('max_pages', 1)), limits['max_pages'])
    max_records = 10 if preview else limits['max_records']
    timeout = min(int(settings.get('request_timeout', 20)), 30)
    delay = max(float(settings.get('request_delay', 1)), limits['min_delay'])
    preset = payload.get('preset', 'universal')

    current_url = validate_url(payload['website_url']).url
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    visited: list[str] = []
    confidence_values: list[float] = []
    metadata: dict[str, Any] = {}

    for page_number in range(1, max_pages + 1):
        if should_stop and should_stop():
            break
        if progress:
            progress(page_number, len(records), f'Downloading static page {page_number}')

        html, final_url, _ = _download_html(current_url, timeout, limits['max_response_bytes'])
        visited.append(final_url)

        if preset == 'contact':
            page_records = extract_contact_information(html, final_url)
            page_warnings: list[str] = []
            confidence_values.append(0.9 if page_records else 0.0)
            metadata.setdefault('dataset_type', 'contact-information')
        elif preset == 'universal':
            auto_result = extract_auto_data(html, final_url, max_records=max_records - len(records))
            page_records = auto_result.records
            page_warnings = auto_result.warnings
            confidence_values.append(auto_result.confidence)
            metadata['dataset_type'] = auto_result.dataset_type
            metadata['auto_details'] = auto_result.details
        else:
            page_records, page_warnings, matched = extract_records(
                html, final_url, payload.get('container_selector', ''),
                payload.get('fields', []), max_records=max_records - len(records)
            )
            confidence_values.append(1.0 if page_records else 0.0)
            metadata['matched_containers'] = matched
            metadata.setdefault('dataset_type', 'custom-selectors')

        records.extend(page_records)
        warnings.extend(page_warnings)
        records = deduplicate_records(records)[:max_records]

        if preview or len(records) >= max_records:
            break

        mode = pagination.get('mode', 'none')
        next_url: str | None = None
        if mode == 'auto':
            next_url = detect_next_url(html, final_url)
        elif mode == 'next':
            selector = pagination.get('next_selector', '')
            soup = BeautifulSoup(html, 'html.parser')
            anchor = soup.select_one(selector) if selector else None
            if anchor and anchor.get('href'):
                next_url = urljoin(final_url, anchor.get('href'))
        elif mode == 'url':
            pattern = pagination.get('url_pattern', '')
            start_page = int(pagination.get('start_page', 1))
            next_index = start_page + page_number
            if pattern and '{page}' in pattern:
                next_url = pattern.format(page=next_index)

        if not next_url or next_url == 'Not Available' or next_url in visited:
            break
        validate_url(next_url)
        current_url = next_url
        time.sleep(delay)

    confidence = min(confidence_values) if confidence_values else 0.0
    return ScrapeResult(
        records=deduplicate_records(records), pages_scraped=len(visited),
        mode_used='static', warnings=sorted(set(warnings)), visited_urls=visited,
        confidence=confidence, metadata=metadata,
    )
