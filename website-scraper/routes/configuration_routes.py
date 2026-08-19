from __future__ import annotations

from flask import Blueprint, jsonify, request

from database.database import (
    create_configuration, delete_configuration, get_configuration,
    get_configurations, update_configuration,
)
from scraper.url_validator import UnsafeURLError, validate_url

configuration_bp = Blueprint('configuration_api', __name__, url_prefix='/api/configurations')


def _validate() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError('A JSON request body is required.')
    if not str(data.get('configuration_name', '')).strip():
        raise ValueError('Configuration name is required.')
    validate_url(data.get('website_url', ''))
    return data


@configuration_bp.get('')
def list_configurations():
    return jsonify({'success': True, 'configurations': get_configurations()})


@configuration_bp.get('/<int:config_id>')
def detail(config_id: int):
    item = get_configuration(config_id)
    if not item:
        return jsonify({'success': False, 'message': 'Configuration not found.'}), 404
    return jsonify({'success': True, 'configuration': item})


@configuration_bp.post('')
def create():
    try:
        data = _validate()
        config_id = create_configuration(data)
        return jsonify({'success': True, 'message': 'Configuration saved.', 'id': config_id}), 201
    except (ValueError, UnsafeURLError) as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400


@configuration_bp.put('/<int:config_id>')
def update(config_id: int):
    try:
        data = _validate()
        if not update_configuration(config_id, data):
            return jsonify({'success': False, 'message': 'Configuration not found.'}), 404
        return jsonify({'success': True, 'message': 'Configuration updated.'})
    except (ValueError, UnsafeURLError) as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400


@configuration_bp.post('/<int:config_id>/duplicate')
def duplicate(config_id: int):
    item = get_configuration(config_id)
    if not item:
        return jsonify({'success': False, 'message': 'Configuration not found.'}), 404
    item['configuration_name'] = f"{item['configuration_name']} Copy"
    new_id = create_configuration(item)
    return jsonify({'success': True, 'message': 'Configuration duplicated.', 'id': new_id}), 201


@configuration_bp.delete('/<int:config_id>')
def remove(config_id: int):
    if not delete_configuration(config_id):
        return jsonify({'success': False, 'message': 'Configuration not found.'}), 404
    return jsonify({'success': True, 'message': 'Configuration deleted.'})
