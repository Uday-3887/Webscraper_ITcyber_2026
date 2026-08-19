from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify

from database.database import delete_job, get_job, get_job_records, get_jobs
from services.job_runner import stop_job

job_bp = Blueprint('job_api', __name__, url_prefix='/api/jobs')


@job_bp.get('')
def list_jobs():
    return jsonify({'success': True, 'jobs': get_jobs(limit=250)})


@job_bp.get('/<int:job_id>')
def job_detail(job_id: int):
    job = get_job(job_id)
    if not job:
        return jsonify({'success': False, 'message': 'Job not found.'}), 404
    records = get_job_records(job_id) if job['status'] in {'completed', 'stopped'} else []
    return jsonify({'success': True, 'job': job, 'records': records})


@job_bp.post('/<int:job_id>/stop')
def stop(job_id: int):
    job = get_job(job_id)
    if not job:
        return jsonify({'success': False, 'message': 'Job not found.'}), 404
    if job['status'] not in {'queued', 'running'}:
        return jsonify({'success': False, 'message': 'This job is not currently running.'}), 409
    if stop_job(job_id):
        return jsonify({'success': True, 'message': 'Stop requested.'})
    return jsonify({'success': False, 'message': 'The worker is no longer active.'}), 409


@job_bp.delete('/<int:job_id>')
def remove_job(job_id: int):
    job = get_job(job_id)
    if not job:
        return jsonify({'success': False, 'message': 'Job not found.'}), 404
    if job['status'] in {'queued', 'running'}:
        stop_job(job_id)
        return jsonify({'success': False, 'message': 'Stop the job and wait before deleting it.'}), 409
    stem = f'{job_id}-'
    export_folder = Path(current_app.config['EXPORT_FOLDER'])
    for file in export_folder.glob(f'{stem}*'):
        if file.is_file():
            file.unlink(missing_ok=True)
    delete_job(job_id)
    return jsonify({'success': True, 'message': 'Job deleted.'})
