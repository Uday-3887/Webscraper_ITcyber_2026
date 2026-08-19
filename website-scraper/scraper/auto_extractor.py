from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

PRICE_RE = re.compile(
    r"(?:₹|Rs\.?|INR|\$|€|£|¥|AED|USD|EUR|GBP)\s?\d[\d,]*(?:\.\d{1,2})?"
    r"|\d[\d,]*(?:\.\d{1,2})?\s?(?:₹|INR|USD|EUR|GBP|AED)",
    re.I,
)
NEXT_TEXT_RE = re.compile(r"^(?:next|next page|older|more|›|»|→)$", re.I)
SKIP_ANCESTORS = {"nav", "header", "footer", "aside", "form"}
GENERIC_CLASSES = {
    "active", "clearfix", "container", "content", "flex", "grid", "hidden", "item",
    "list", "row", "show", "wrapper",
}


@dataclass
class AutoExtractionResult:
    records: list[dict[str, Any]]
    dataset_type: str
    confidence: float
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


def _clean(value: Any, limit: int = 800) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text[:limit]


def _absolute(base_url: str, value: str | None) -> str:
    if not value:
        return "Not Available"
    resolved = urljoin(base_url, value.strip())
    parsed = urlparse(resolved)
    return resolved if parsed.scheme in {"http", "https"} else "Not Available"


def _is_visible_content(tag: Tag) -> bool:
    if tag.name in {"script", "style", "noscript", "template", "svg"}:
        return False
    if tag.has_attr("hidden"):
        return False
    style = str(tag.get("style", "")).replace(" ", "").lower()
    if "display:none" in style or "visibility:hidden" in style:
        return False
    return not any(parent.name in SKIP_ANCESTORS for parent in tag.parents if isinstance(parent, Tag))


def _flatten_json(value: Any, prefix: str = "", depth: int = 0) -> dict[str, str]:
    if depth > 3:
        return {prefix or "value": _clean(json.dumps(value, ensure_ascii=False), 500)}
    output: dict[str, str] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).startswith("@context"):
                continue
            name = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(child, dict):
                output.update(_flatten_json(child, name, depth + 1))
            elif isinstance(child, list):
                scalar_values = [item for item in child if not isinstance(item, (dict, list))]
                if len(scalar_values) == len(child):
                    output[name] = _clean(", ".join(map(str, scalar_values)), 500)
                else:
                    output[name] = _clean(json.dumps(child, ensure_ascii=False), 500)
            else:
                output[name] = _clean(child, 500) or "Not Available"
    else:
        output[prefix or "value"] = _clean(value, 500)
    return output


def _walk_json_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _walk_json_objects(item)
        item_list = value.get("itemListElement")
        if isinstance(item_list, list):
            for item in item_list:
                if isinstance(item, dict) and isinstance(item.get("item"), dict):
                    yield item["item"]
                elif isinstance(item, dict):
                    yield item
        if any(key in value for key in ("@type", "name", "headline", "url", "offers")):
            yield value
        for child in value.values():
            if isinstance(child, (dict, list)):
                yield from _walk_json_objects(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json_objects(item)


def _json_ld_dataset(soup: BeautifulSoup, base_url: str, max_records: int) -> AutoExtractionResult | None:
    objects: list[dict[str, Any]] = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        objects.extend(_walk_json_objects(parsed))

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for obj in objects:
        row = _flatten_json(obj)
        if not row:
            continue
        for key in list(row):
            if key.lower().endswith(("url", "image", "logo")) and row[key] != "Not Available":
                row[key] = _absolute(base_url, row[key])
        signature = json.dumps(row, sort_keys=True, ensure_ascii=False)
        if signature not in seen:
            seen.add(signature)
            rows.append({"Record Type": "JSON-LD", **row})
        if len(rows) >= max_records:
            break

    if not rows:
        return None
    meaningful = sum(1 for row in rows if any(k.lower().endswith(("name", "headline", "url", "price")) for k in row))
    useful_types = {
        'product', 'article', 'newsarticle', 'blogposting', 'event', 'jobposting',
        'localbusiness', 'restaurant', 'hotel', 'offer', 'course', 'recipe'
    }
    typed = 0
    for row in rows:
        type_value = str(row.get('@type', row.get('type', ''))).lower()
        if any(item in type_value for item in useful_types):
            typed += 1
    confidence = 0.48 + min(len(rows), 20) * 0.018
    if meaningful:
        confidence += 0.06
    if typed:
        confidence += 0.08
    if len(rows) >= 3:
        confidence += 0.08
    confidence = min(0.94, confidence)
    return AutoExtractionResult(
        records=rows,
        dataset_type="json-ld",
        confidence=confidence,
        warnings=[f"Auto-detected {len(rows)} structured JSON-LD record(s)."],
        details={"record_count": len(rows)},
    )


def _table_dataset(soup: BeautifulSoup, max_records: int) -> AutoExtractionResult | None:
    best: tuple[float, list[dict[str, str]], int] | None = None
    for table_index, table in enumerate(soup.select("table"), start=1):
        rows = table.select("tr")
        if len(rows) < 2:
            continue
        header_cells = rows[0].select("th, td")
        headers = [_clean(cell.get_text(" ", strip=True), 120) or f"Column {i + 1}" for i, cell in enumerate(header_cells)]
        if len(set(headers)) != len(headers):
            headers = [f"{name} {i + 1}" for i, name in enumerate(headers)]
        data: list[dict[str, str]] = []
        for tr in rows[1:]:
            cells = tr.select("th, td")
            if not cells:
                continue
            if len(cells) > len(headers):
                headers.extend(f"Column {i + 1}" for i in range(len(headers), len(cells)))
            record = {headers[i]: _clean(cell.get_text(" ", strip=True)) or "Not Available" for i, cell in enumerate(cells)}
            if any(value != "Not Available" for value in record.values()):
                data.append({"Record Type": "HTML Table", **record})
            if len(data) >= max_records:
                break
        if not data:
            continue
        score = len(data) * max(2, len(headers))
        if best is None or score > best[0]:
            best = (score, data, table_index)
    if best is None:
        return None
    _, records, table_index = best
    return AutoExtractionResult(
        records=records,
        dataset_type="html-table",
        confidence=min(0.99, 0.72 + min(len(records), 20) * 0.012),
        warnings=[f"Auto-detected HTML table #{table_index} with {len(records)} row(s)."],
        details={"table_index": table_index, "record_count": len(records)},
    )


def _signature(tag: Tag) -> tuple[str, tuple[str, ...]]:
    classes = []
    for value in tag.get("class", []):
        normalized = re.sub(r"\d+", "#", str(value).lower())
        if normalized and normalized not in GENERIC_CLASSES and len(normalized) <= 60:
            classes.append(normalized)
    return tag.name, tuple(sorted(classes)[:4])


def _record_from_card(tag: Tag, base_url: str) -> dict[str, str]:
    heading = tag.select_one("h1, h2, h3, h4, h5, [class*='title'], [class*='name'], strong")
    link = tag.select_one("a[href]")
    image = tag.select_one("img[src], img[data-src], source[srcset]")
    full_text = _clean(tag.get_text(" ", strip=True), 900)
    price_match = PRICE_RE.search(full_text)

    description = "Not Available"
    paragraph = tag.select_one("p, [class*='description'], [class*='summary'], [class*='excerpt']")
    if paragraph:
        description = _clean(paragraph.get_text(" ", strip=True), 500) or "Not Available"
    elif full_text:
        title_text = _clean(heading.get_text(" ", strip=True), 250) if heading else ""
        description = _clean(full_text.replace(title_text, "", 1), 500) or "Not Available"

    image_value = "Not Available"
    image_alt = "Not Available"
    if image:
        raw_image = image.get("src") or image.get("data-src") or str(image.get("srcset", "")).split(" ")[0]
        image_value = _absolute(base_url, raw_image)
        image_alt = _clean(image.get("alt"), 200) or "Not Available"

    return {
        "Record Type": "Repeated Item",
        "Title": _clean(heading.get_text(" ", strip=True), 300) if heading else (_clean(link.get_text(" ", strip=True), 300) if link else "Not Available"),
        "Description": description,
        "Price": price_match.group(0) if price_match else "Not Available",
        "URL": _absolute(base_url, link.get("href")) if link else "Not Available",
        "Image URL": image_value,
        "Image Alt": image_alt,
    }


def _card_dataset(soup: BeautifulSoup, base_url: str, max_records: int) -> AutoExtractionResult | None:
    groups: dict[tuple[str, tuple[str, ...]], list[Tag]] = {}
    candidates = soup.select("article, li, div, section")
    for tag in candidates:
        if not _is_visible_content(tag):
            continue
        text = _clean(tag.get_text(" ", strip=True), 1200)
        if len(text) < 8 or len(text) > 1500:
            continue
        signature = _signature(tag)
        if tag.name == "div" and not signature[1]:
            continue
        groups.setdefault(signature, []).append(tag)

    best_score = 0.0
    best_records: list[dict[str, str]] = []
    best_signature: tuple[str, tuple[str, ...]] | None = None
    for signature, tags in groups.items():
        if not 3 <= len(tags) <= 500:
            continue
        # Prefer peer elements rather than nested copies of the same signature.
        selected: list[Tag] = []
        for tag in tags:
            if any(_signature(parent) == signature for parent in tag.parents if isinstance(parent, Tag)):
                continue
            selected.append(tag)
        if len(selected) < 3:
            selected = tags

        records = [_record_from_card(tag, base_url) for tag in selected[:max_records]]
        useful = [
            row for row in records
            if row["Title"] != "Not Available"
            and any(row[key] != "Not Available" for key in ("URL", "Price", "Description", "Image URL"))
        ]
        if len(useful) < 3:
            continue
        unique_titles = len({row["Title"] for row in useful})
        link_ratio = sum(row["URL"] != "Not Available" for row in useful) / len(useful)
        image_ratio = sum(row["Image URL"] != "Not Available" for row in useful) / len(useful)
        price_ratio = sum(row["Price"] != "Not Available" for row in useful) / len(useful)
        score = len(useful) * 2.0 + unique_titles * 1.5 + link_ratio * 8 + image_ratio * 5 + price_ratio * 8
        if signature[0] in {"article", "li"}:
            score += 5
        if score > best_score:
            best_score = score
            best_records = useful
            best_signature = signature

    if not best_records or best_signature is None:
        return None
    selector_hint = best_signature[0]
    if best_signature[1]:
        selector_hint += "." + ".".join(best_signature[1])
    confidence = min(0.94, 0.55 + min(len(best_records), 30) * 0.012 + min(best_score, 80) / 500)
    return AutoExtractionResult(
        records=best_records,
        dataset_type="repeated-items",
        confidence=confidence,
        warnings=[f"Auto-detected {len(best_records)} repeated item(s) using a structure similar to `{selector_hint}`."],
        details={"selector_hint": selector_hint, "record_count": len(best_records)},
    )


def _links_dataset(soup: BeautifulSoup, base_url: str, max_records: int) -> AutoExtractionResult | None:
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    host = urlparse(base_url).netloc
    for anchor in soup.select("main a[href], article a[href], body a[href]"):
        if not _is_visible_content(anchor):
            continue
        url = _absolute(base_url, anchor.get("href"))
        text = _clean(anchor.get_text(" ", strip=True), 300)
        if url == "Not Available" or not text or url in seen:
            continue
        seen.add(url)
        records.append({
            "Record Type": "Link",
            "Link Text": text,
            "URL": url,
            "Internal Link": "Yes" if urlparse(url).netloc == host else "No",
        })
        if len(records) >= max_records:
            break
    if len(records) < 2:
        return None
    return AutoExtractionResult(
        records=records,
        dataset_type="links",
        confidence=0.42,
        warnings=["No strong table or repeated-card dataset was found; exported visible links instead."],
        details={"record_count": len(records)},
    )


def _page_fallback(soup: BeautifulSoup, base_url: str) -> AutoExtractionResult:
    title = _clean(soup.title.get_text(" ", strip=True), 300) if soup.title else "Not Available"
    h1 = soup.select_one("h1")
    description = soup.select_one('meta[name="description"], meta[property="og:description"]')
    paragraphs = [
        _clean(p.get_text(" ", strip=True), 600)
        for p in soup.select("main p, article p, body p")
        if _is_visible_content(p) and len(_clean(p.get_text(" ", strip=True))) >= 30
    ][:20]
    record = {
        "Record Type": "Page Summary",
        "Page Title": title,
        "Main Heading": _clean(h1.get_text(" ", strip=True), 300) if h1 else "Not Available",
        "Meta Description": _clean(description.get("content"), 500) if description else "Not Available",
        "Page URL": base_url,
        "Visible Text": _clean(" ".join(paragraphs), 5000) or "Not Available",
    }
    return AutoExtractionResult(
        records=[record],
        dataset_type="page-summary",
        confidence=0.25,
        warnings=["Only a page summary could be detected. The page may require JavaScript or custom CSS selectors."],
        details={"record_count": 1},
    )


def extract_auto_data(html: str, base_url: str, max_records: int = 5000) -> AutoExtractionResult:
    soup = BeautifulSoup(html, "html.parser")
    capped = max(1, max_records)

    candidates = [
        result for result in (
            _table_dataset(soup, capped),
            _json_ld_dataset(soup, base_url, capped),
            _card_dataset(soup, base_url, capped),
        )
        if result is not None
    ]
    if candidates:
        # Confidence is a better signal than raw record count because one strong table
        # should beat hundreds of navigation links.
        return max(candidates, key=lambda item: (item.confidence, len(item.records)))

    links = _links_dataset(soup, base_url, capped)
    if links:
        return links
    return _page_fallback(soup, base_url)


def detect_next_url(html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    candidates = [
        soup.select_one('link[rel="next"][href]'),
        soup.select_one('a[rel="next"][href]'),
        soup.select_one('a[aria-label*="next" i][href]'),
        soup.select_one('a[class*="next" i][href]'),
    ]
    for candidate in candidates:
        if candidate and candidate.get("href"):
            return _absolute(base_url, candidate.get("href"))
    for anchor in soup.select("a[href]"):
        text = _clean(anchor.get_text(" ", strip=True), 60)
        if NEXT_TEXT_RE.match(text):
            return _absolute(base_url, anchor.get("href"))
    return None
