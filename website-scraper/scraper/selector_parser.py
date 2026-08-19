from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

EMAIL_RE = re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', re.I)
PHONE_RE = re.compile(r'(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)')


def _clean(value: Any) -> str:
    return ' '.join(str(value or '').split()).strip()




def _select_one(container: Tag, selector: str) -> Tag | None:
    parts = [part.strip() for part in selector.split(',')]
    if ':scope' in parts:
        return container
    return container.select_one(selector)

def _extract(element: Tag, field: dict[str, Any], base_url: str) -> str:
    extraction = field.get('extraction_type', 'text')
    if extraction == 'html':
        return str(element)
    if extraction in {'attribute', 'link', 'image'}:
        attribute = field.get('attribute_name')
        if extraction == 'link':
            attribute = attribute or 'href'
        elif extraction == 'image':
            attribute = attribute or 'src'
        value = element.get(attribute or '')
        if isinstance(value, list):
            value = ' '.join(value)
        if extraction in {'link', 'image'} or attribute in {'href', 'src'}:
            return urljoin(base_url, str(value or ''))
        return _clean(value)
    return _clean(element.get_text(' ', strip=True))


def extract_records(
    html: str,
    base_url: str,
    container_selector: str,
    fields: list[dict[str, Any]],
    max_records: int = 5000,
) -> tuple[list[dict[str, str]], list[str], int]:
    soup = BeautifulSoup(html, 'html.parser')
    warnings: list[str] = []

    if container_selector:
        containers = soup.select(container_selector)
    else:
        containers = [soup]

    if not containers:
        return [], [f'Container selector not found: {container_selector}'], 0

    records: list[dict[str, str]] = []
    missing_counts: dict[str, int] = {}

    for container in containers[:max_records]:
        record: dict[str, str] = {}
        has_value = False
        for field in fields:
            name = _clean(field.get('field_name')) or 'field'
            selector = _clean(field.get('selector'))
            if not selector:
                record[name] = 'Not Available'
                missing_counts[name] = missing_counts.get(name, 0) + 1
                continue
            element = _select_one(container, selector)
            if element is None:
                record[name] = 'Not Available'
                missing_counts[name] = missing_counts.get(name, 0) + 1
                continue
            value = _extract(element, field, base_url) or 'Not Available'
            record[name] = value
            has_value = has_value or value != 'Not Available'
        if has_value and record:
            records.append(record)

    for name, count in missing_counts.items():
        if count == len(containers):
            warnings.append(f'No matches found for field: {name}')
        elif count:
            warnings.append(f'{name} was missing in {count} record(s).')

    return records, warnings, len(containers)


def extract_contact_information(html: str, base_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, 'html.parser')
    visible_text = soup.get_text(' ', strip=True)
    emails = sorted(set(EMAIL_RE.findall(visible_text)))
    phones = sorted({_clean(item) for item in PHONE_RE.findall(visible_text)})
    websites: set[str] = set()
    social: set[str] = set()
    for anchor in soup.select('a[href]'):
        href = urljoin(base_url, anchor.get('href', ''))
        if href.startswith(('http://', 'https://')):
            if any(domain in href.lower() for domain in (
                'facebook.com', 'instagram.com', 'linkedin.com', 'x.com', 'twitter.com', 'youtube.com'
            )):
                social.add(href)
            else:
                websites.add(href)
    return [{
        'Emails': ', '.join(emails) or 'Not Available',
        'Phone Numbers': ', '.join(phones) or 'Not Available',
        'Website Links': ', '.join(sorted(websites)[:50]) or 'Not Available',
        'Social Links': ', '.join(sorted(social)[:50]) or 'Not Available',
    }]


def deduplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[tuple[str, str], ...]] = set()
    unique: list[dict[str, Any]] = []
    for record in records:
        key = tuple(sorted((str(k), str(v)) for k, v in record.items()))
        if key not in seen:
            seen.add(key)
            unique.append(record)
    return unique
