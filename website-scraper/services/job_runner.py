from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from time import monotonic
from typing import Any

from flask import Flask

from database.database import add_records, create_job, get_job, update_job
from scraper.dynamic_scraper import scrape_dynamic
from scraper.exporters import export_all
from scraper.static_scraper import ScrapeError, ScrapeResult, scrape_static
from scraper.url_validator import validate_url
from scraper.site_crawler import crawl_site

logger = logging.getLogger(__name__)
_CONTROLS: dict[int, threading.Event] = {}
_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _limits(app: Flask) -> dict[str, Any]:
    return {
        'max_pages': app.config['MAX_PAGES'],
        'max_records': app.config['MAX_RECORDS'],
        'min_delay': app.config['MIN_REQUEST_DELAY'],
        'max_response_bytes': app.config['MAX_RESPONSE_BYTES'],
        'browser_timeout': app.config['DEFAULT_BROWSER_TIMEOUT'],
        'max_job_seconds': app.config['MAX_JOB_SECONDS'],
        'max_load_more_clicks': app.config['MAX_LOAD_MORE_CLICKS'],
        'max_scroll_count': app.config['MAX_SCROLL_COUNT'],
        'headless': app.config['PLAYWRIGHT_HEADLESS'],
    }


def start_scraping_job(app: Flask, payload: dict[str, Any]) -> int:
    validate_url(payload.get('website_url', ''))
    job_id = create_job(payload)
    stop_event = threading.Event()
    with _LOCK:
        _CONTROLS[job_id] = stop_event
    thread = threading.Thread(
        target=_run_job, args=(app, job_id, payload, stop_event),
        name=f'scrape-job-{job_id}', daemon=True,
    )
    thread.start()
    return job_id


def stop_job(job_id: int) -> bool:
    with _LOCK:
        event = _CONTROLS.get(job_id)
    if event:
        event.set()
        return True
    return False


def _run_job(app: Flask, job_id: int, payload: dict[str, Any], stop_event: threading.Event) -> None:
    started = monotonic()
    with app.app_context():
        update_job(job_id, status='running', started_at=utc_now(), progress_message='Starting scraper')

        def should_stop() -> bool:
            return stop_event.is_set() or monotonic() - started > app.config['MAX_JOB_SECONDS']

        def progress(page: int, count: int, message: str) -> None:
            update_job(job_id, pages_scraped=page, records_extracted=count, progress_message=message)

        try:
            limits = _limits(app)
            mode = payload.get('scraping_mode', 'auto')
            result: ScrapeResult
            if payload.get('full_site'):
                result = crawl_site(payload, limits, should_stop=should_stop, progress=progress)
            elif mode == 'static':
                result = scrape_static(payload, limits, should_stop=should_stop, progress=progress)
            elif mode == 'dynamic':
                result = scrape_dynamic(payload, limits, should_stop=should_stop, progress=progress)
            else:
                # Auto mode prefers the light static client, but HTTP 403 and other
                # request-layer blocks are retried once with a normal Playwright browser.
                # This is rendering fallback only; CAPTCHA/login/access controls are never bypassed.
                static_result: ScrapeResult | None = None
                try:
                    static_result = scrape_static(
                        payload, limits, should_stop=should_stop, progress=progress
                    )
                    result = static_result
                except ScrapeError as exc:
                    message = str(exc).lower()
                    browser_fallback_errors = (
                        'http 403', 'blocked automated access', 'unsupported content type',
                        'ssl certificate', 'timed out',
                    )
                    if not any(item in message for item in browser_fallback_errors) or should_stop():
                        raise
                    progress(0, 0, 'Static request was blocked; opening the public page in Playwright')
                    result = scrape_dynamic(
                        payload, limits, should_stop=should_stop, progress=progress
                    )

                if (not result.records or result.confidence < 0.45) and not should_stop():
                    progress(0, 0, 'Static extraction was incomplete; rendering the page with Playwright')
                    try:
                        dynamic_result = scrape_dynamic(
                            payload, limits, should_stop=should_stop, progress=progress
                        )
                        if dynamic_result.records and dynamic_result.confidence >= result.confidence:
                            result = dynamic_result
                    except ScrapeError as exc:
                        if not result.records:
                            raise
                        result.warnings.append(
                            f'Dynamic rendering was unavailable; exported the static result: {exc}'
                        )

            if stop_event.is_set():
                output_file = None
                if result.records:
                    add_records(job_id, result.records)
                    exported = export_all(
                        result.records, app.config['EXPORT_FOLDER'], job_id,
                        payload.get('job_name', f'job-{job_id}')
                    )
                    output_file = exported['csv']
                update_job(
                    job_id, status='stopped', mode_used=f"{result.mode_used} / {result.metadata.get('dataset_type', 'custom')}",
                    pages_scraped=result.pages_scraped, records_extracted=len(result.records),
                    output_file=output_file,
                    progress_message='Stopped by user', completed_at=utc_now(),
                )
                return

            if monotonic() - started > app.config['MAX_JOB_SECONDS']:
                raise ScrapeError('The job exceeded the maximum runtime limit.')
            if not result.records:
                raise ScrapeError('No public records were found. Try Dynamic mode or add custom CSS selectors.')

            add_records(job_id, result.records)
            exported = export_all(
                result.records, app.config['EXPORT_FOLDER'], job_id,
                payload.get('job_name', f'job-{job_id}')
            )
            update_job(
                job_id, status='completed', mode_used=f"{result.mode_used} / {result.metadata.get('dataset_type', 'custom')}",
                pages_scraped=result.pages_scraped, records_extracted=len(result.records),
                output_file=exported['csv'], error_message='\n'.join(result.warnings[:20]) or None,
                progress_message='Scraping completed successfully', completed_at=utc_now(),
            )
            logger.info('job=%s status=completed mode=%s pages=%s records=%s',
                        job_id, result.mode_used, result.pages_scraped, len(result.records))
        except Exception as exc:
            logger.exception('job=%s status=failed error=%s', job_id, exc)
            update_job(
                job_id, status='failed', error_message=str(exc),
                progress_message='Scraping failed', completed_at=utc_now(),
            )
        finally:
            with _LOCK:
                _CONTROLS.pop(job_id, None)
