from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, send_file

from database.database import get_job

export_bp = Blueprint('export_api', __name__, url_prefix='/api/export')


@export_bp.get('/<int:job_id>/<string:file_type>')
def download(job_id: int, file_type: str):
    extension_map = {'csv': 'csv', 'json': 'json', 'excel': 'xlsx'}
    extension = extension_map.get(file_type)
    if not extension:
        return jsonify({'success': False, 'message': 'Unsupported export format.'}), 400
    job = get_job(job_id)
    if not job or job.get('status') not in {'completed', 'stopped'}:
        return jsonify({'success': False, 'message': 'Completed job not found.'}), 404
    folder = Path(current_app.config['EXPORT_FOLDER']).resolve()
    matches = list(folder.glob(f'{job_id}-*.{extension}'))
    if not matches:
        return jsonify({'success': False, 'message': 'Export file not found.'}), 404
    path = matches[0].resolve()
    if folder not in path.parents:
        return jsonify({'success': False, 'message': 'Invalid export path.'}), 400
    return send_file(path, as_attachment=True, download_name=path.name)
