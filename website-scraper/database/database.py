from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from flask import current_app


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def db_path() -> str:
    return current_app.config['DATABASE_PATH']


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    path = Path(db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    schema = '''
    CREATE TABLE IF NOT EXISTS scraping_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_name TEXT NOT NULL,
        website_url TEXT NOT NULL,
        scraping_mode TEXT NOT NULL,
        mode_used TEXT,
        status TEXT NOT NULL DEFAULT 'queued',
        pages_scraped INTEGER NOT NULL DEFAULT 0,
        records_extracted INTEGER NOT NULL DEFAULT 0,
        output_file TEXT,
        error_message TEXT,
        progress_message TEXT,
        started_at TEXT,
        completed_at TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS scraper_configurations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        configuration_name TEXT NOT NULL,
        website_url TEXT NOT NULL,
        scraping_mode TEXT NOT NULL,
        container_selector TEXT,
        fields_json TEXT NOT NULL,
        pagination_json TEXT NOT NULL,
        settings_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS scraped_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        record_data_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(job_id) REFERENCES scraping_jobs(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON scraping_jobs(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON scraping_jobs(status);
    CREATE INDEX IF NOT EXISTS idx_records_job_id ON scraped_records(job_id);
    CREATE INDEX IF NOT EXISTS idx_configs_updated_at ON scraper_configurations(updated_at DESC);
    '''
    with connection() as conn:
        conn.executescript(schema)


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def create_job(payload: dict[str, Any]) -> int:
    with connection() as conn:
        cursor = conn.execute(
            '''INSERT INTO scraping_jobs
               (job_name, website_url, scraping_mode, status, progress_message, created_at)
               VALUES (?, ?, ?, 'queued', 'Waiting to start', ?)''',
            (
                payload.get('job_name') or 'Untitled scraping job',
                payload['website_url'],
                payload.get('scraping_mode', 'auto'),
                utc_now(),
            ),
        )
        return int(cursor.lastrowid)


def update_job(job_id: int, **values: Any) -> None:
    allowed = {
        'mode_used', 'status', 'pages_scraped', 'records_extracted', 'output_file',
        'error_message', 'progress_message', 'started_at', 'completed_at'
    }
    clean = {key: value for key, value in values.items() if key in allowed}
    if not clean:
        return
    assignments = ', '.join(f'{key} = ?' for key in clean)
    with connection() as conn:
        conn.execute(
            f'UPDATE scraping_jobs SET {assignments} WHERE id = ?',
            [*clean.values(), job_id],
        )


def add_records(job_id: int, records: list[dict[str, Any]]) -> None:
    now = utc_now()
    with connection() as conn:
        conn.executemany(
            'INSERT INTO scraped_records (job_id, record_data_json, created_at) VALUES (?, ?, ?)',
            [(job_id, json.dumps(record, ensure_ascii=False), now) for record in records],
        )


def get_job(job_id: int) -> dict[str, Any] | None:
    with connection() as conn:
        return _row(conn.execute('SELECT * FROM scraping_jobs WHERE id = ?', (job_id,)).fetchone())


def get_jobs(limit: int = 100) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            'SELECT * FROM scraping_jobs ORDER BY id DESC LIMIT ?', (max(1, min(limit, 500)),)
        ).fetchall()
        return [dict(row) for row in rows]


def get_job_records(job_id: int, limit: int = 5000) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            'SELECT record_data_json FROM scraped_records WHERE job_id = ? ORDER BY id LIMIT ?',
            (job_id, max(1, min(limit, 5000))),
        ).fetchall()
    return [json.loads(row['record_data_json']) for row in rows]


def delete_job(job_id: int) -> bool:
    with connection() as conn:
        cursor = conn.execute('DELETE FROM scraping_jobs WHERE id = ?', (job_id,))
        return cursor.rowcount > 0


def get_stats() -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute('''
            SELECT
                COUNT(*) AS total_jobs,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS successful_jobs,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_jobs,
                COALESCE(SUM(records_extracted), 0) AS total_records,
                MAX(created_at) AS latest_scrape
            FROM scraping_jobs
        ''').fetchone()
        return dict(row)


def create_configuration(payload: dict[str, Any]) -> int:
    now = utc_now()
    with connection() as conn:
        cursor = conn.execute(
            '''INSERT INTO scraper_configurations
               (configuration_name, website_url, scraping_mode, container_selector,
                fields_json, pagination_json, settings_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                payload['configuration_name'], payload['website_url'],
                payload.get('scraping_mode', 'auto'), payload.get('container_selector', ''),
                json.dumps(payload.get('fields', []), ensure_ascii=False),
                json.dumps(payload.get('pagination', {}), ensure_ascii=False),
                json.dumps({**payload.get('settings', {}), '_preset': payload.get('preset', 'universal')}, ensure_ascii=False),
                now, now,
            ),
        )
        return int(cursor.lastrowid)


def _decode_config(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if not row:
        return None
    item = dict(row)
    item['fields'] = json.loads(item.pop('fields_json') or '[]')
    item['pagination'] = json.loads(item.pop('pagination_json') or '{}')
    item['settings'] = json.loads(item.pop('settings_json') or '{}')
    item['preset'] = item['settings'].pop('_preset', 'universal')
    return item


def get_configuration(config_id: int) -> dict[str, Any] | None:
    with connection() as conn:
        return _decode_config(conn.execute(
            'SELECT * FROM scraper_configurations WHERE id = ?', (config_id,)
        ).fetchone())


def get_configurations() -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            'SELECT * FROM scraper_configurations ORDER BY updated_at DESC'
        ).fetchall()
        return [_decode_config(row) for row in rows if row]


def update_configuration(config_id: int, payload: dict[str, Any]) -> bool:
    with connection() as conn:
        cursor = conn.execute(
            '''UPDATE scraper_configurations SET
               configuration_name = ?, website_url = ?, scraping_mode = ?, container_selector = ?,
               fields_json = ?, pagination_json = ?, settings_json = ?, updated_at = ?
               WHERE id = ?''',
            (
                payload['configuration_name'], payload['website_url'],
                payload.get('scraping_mode', 'auto'), payload.get('container_selector', ''),
                json.dumps(payload.get('fields', []), ensure_ascii=False),
                json.dumps(payload.get('pagination', {}), ensure_ascii=False),
                json.dumps({**payload.get('settings', {}), '_preset': payload.get('preset', 'universal')}, ensure_ascii=False),
                utc_now(), config_id,
            ),
        )
        return cursor.rowcount > 0


def delete_configuration(config_id: int) -> bool:
    with connection() as conn:
        return conn.execute(
            'DELETE FROM scraper_configurations WHERE id = ?', (config_id,)
        ).rowcount > 0
