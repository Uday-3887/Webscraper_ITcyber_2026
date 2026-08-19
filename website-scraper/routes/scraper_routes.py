from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from scraper.dynamic_scraper import scrape_dynamic
from scraper.robots_checker import check_robots
from scraper.static_scraper import ScrapeError, scrape_static
from scraper.url_validator import UnsafeURLError, validate_url
from services.job_runner import start_scraping_job

scraper_bp = Blueprint('scraper_api', __name__, url_prefix='/api')


def _payload() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError('A JSON request body is required.')
    validate_url(data.get('website_url', ''))
    fields = data.get('fields', [])
    if not isinstance(fields, list):
        raise ValueError('Extraction fields must be a list.')
    preset = data.get('preset', 'universal')
    if preset not in {'universal', 'contact'} and not fields:
        raise ValueError('Add at least one extraction field or choose Universal Auto Extract.')
    return data


def _limits() -> dict:
    return {
        'max_pages': current_app.config['MAX_PAGES'],
        'max_records': current_app.config['MAX_RECORDS'],
        'min_delay': current_app.config['MIN_REQUEST_DELAY'],
        'max_response_bytes': current_app.config['MAX_RESPONSE_BYTES'],
        'browser_timeout': current_app.config['DEFAULT_BROWSER_TIMEOUT'],
        'max_job_seconds': current_app.config['MAX_JOB_SECONDS'],
        'max_load_more_clicks': current_app.config['MAX_LOAD_MORE_CLICKS'],
        'max_scroll_count': current_app.config['MAX_SCROLL_COUNT'],
        'headless': current_app.config['PLAYWRIGHT_HEADLESS'],
    }


@scraper_bp.post('/preview')
def preview():
    try:
        data = _payload()
        mode = data.get('scraping_mode', 'auto')
        if mode == 'dynamic':
            result = scrape_dynamic(data, _limits(), preview=True)
        else:
            result = scrape_static(data, _limits(), preview=True)
            if mode == 'auto' and (not result.records or result.confidence < 0.45):
                static_result = result
                try:
                    dynamic_result = scrape_dynamic(data, _limits(), preview=True)
                    if dynamic_result.records and dynamic_result.confidence >= static_result.confidence:
                        result = dynamic_result
                except ScrapeError as exc:
                    if not static_result.records:
                        raise
                    static_result.warnings.append(
                        f'Dynamic rendering was unavailable; returning the static result: {exc}'
                    )
                    result = static_result
        return jsonify({
            'success': True,
            'message': 'Preview completed',
            'records': result.records,
            'record_count': len(result.records),
            'pages_scraped': result.pages_scraped,
            'mode_used': result.mode_used,
            'warnings': result.warnings,
            'confidence': round(result.confidence, 2),
            'dataset_type': result.metadata.get('dataset_type', 'custom-selectors'),
            'details': result.metadata,
        })
    except (ValueError, UnsafeURLError, ScrapeError) as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400
    except Exception:
        current_app.logger.exception('Preview failed')
        return jsonify({'success': False, 'message': 'Preview failed due to an unexpected server error.'}), 500


@scraper_bp.post('/scrape')
def scrape():
    try:
        data = _payload()
        app = current_app._get_current_object()
        job_id = start_scraping_job(app, data)
        return jsonify({
            'success': True,
            'message': 'Scraping job started',
            'job_id': job_id,
            'status_url': f'/api/jobs/{job_id}',
        }), 202
    except (ValueError, UnsafeURLError) as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400


@scraper_bp.post('/robots')
def robots():
    try:
        data = request.get_json(silent=True) or {}
        return jsonify({'success': True, 'result': check_robots(data.get('website_url', ''))})
    except (ValueError, UnsafeURLError) as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400
