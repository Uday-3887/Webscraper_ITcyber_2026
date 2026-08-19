from __future__ import annotations
import time
from collections import deque
from urllib.parse import urljoin, urldefrag, urlparse
import requests
from bs4 import BeautifulSoup
from scraper.url_validator import validate_url
from scraper.auto_extractor import extract_auto_data
from scraper.static_scraper import ScrapeError, ScrapeResult

SKIP_EXTENSIONS = {'.jpg','.jpeg','.png','.gif','.webp','.svg','.pdf','.zip','.rar','.7z','.mp4','.mp3','.avi','.css','.js','.xml','.json'}

def _normalize(url: str) -> str:
    clean, _ = urldefrag(url)
    p = urlparse(clean)
    path = p.path or '/'
    return p._replace(path=path.rstrip('/') or '/', fragment='').geturl()

def _same_site(url: str, root_host: str) -> bool:
    host = (urlparse(url).hostname or '').lower()
    return host == root_host or host.endswith('.' + root_host)

def _discover_sitemap(start_url: str, timeout: int) -> list[str]:
    root = f"{urlparse(start_url).scheme}://{urlparse(start_url).netloc}"
    urls=[]
    try:
        r=requests.get(root+'/sitemap.xml',timeout=timeout,headers={'User-Agent':'Mozilla/5.0'},allow_redirects=True)
        if r.ok and '<loc>' in r.text:
            soup=BeautifulSoup(r.text,'xml')
            urls=[x.get_text(strip=True) for x in soup.find_all('loc')]
    except requests.RequestException:
        pass
    return urls

def crawl_site(payload, limits, should_stop=lambda:False, progress=lambda *a:None):
    start=_normalize(validate_url(payload['website_url']))
    root_host=(urlparse(start).hostname or '').lower()
    max_pages=min(int(payload.get('max_pages') or limits['max_pages']), limits['max_pages'])
    max_records=limits['max_records']; delay=max(float(payload.get('request_delay') or 1), limits['min_delay'])
    timeout=min(int(payload.get('request_timeout') or 20),30)
    queue=deque([start]); queued={start}; visited=set(); records=[]; warnings=[]
    for u in _discover_sitemap(start, timeout):
        try:
            n=_normalize(validate_url(u))
            if _same_site(n,root_host) and n not in queued: queue.append(n); queued.add(n)
        except Exception: pass
    session=requests.Session(); session.headers.update({'User-Agent':'Mozilla/5.0 (compatible; ScrapeFlowSiteCrawler/1.0)'})
    while queue and len(visited)<max_pages and len(records)<max_records:
        if should_stop(): break
        url=queue.popleft()
        if url in visited: continue
        visited.add(url); progress(len(visited),len(records),f'Crawling page {len(visited)}: {url}')
        try:
            validate_url(url)
            r=session.get(url,timeout=timeout,allow_redirects=True)
            if r.status_code in {401,403,429}: warnings.append(f'{url}: HTTP {r.status_code} skipped'); continue
            r.raise_for_status()
            if 'text/html' not in r.headers.get('content-type','').lower(): continue
            soup=BeautifulSoup(r.text,'html.parser')
            extracted=extract_auto_data(r.text, url, max_records=max_records-len(records))
            page_records=extracted.records or [{'page_title': soup.title.get_text(strip=True) if soup.title else '', 'page_url':url}]
            for rec in page_records:
                rec={'source_page':url, **rec}; records.append(rec)
                if len(records)>=max_records: break
            for a in soup.select('a[href]'):
                href=a.get('href','').strip()
                if not href or href.startswith(('mailto:','tel:','javascript:','#')): continue
                n=_normalize(urljoin(url,href)); path=urlparse(n).path.lower()
                if any(path.endswith(ext) for ext in SKIP_EXTENSIONS): continue
                if _same_site(n,root_host) and n not in queued and n not in visited:
                    try: validate_url(n); queue.append(n); queued.add(n)
                    except Exception: pass
        except requests.RequestException as exc:
            warnings.append(f'{url}: {exc}')
        time.sleep(delay)
    return ScrapeResult(records=records,pages_scraped=len(visited),mode_used='full-site static crawler',warnings=warnings,confidence=0.9 if records else 0.0,metadata={'dataset_type':'full-site','visited_urls':list(visited)})
