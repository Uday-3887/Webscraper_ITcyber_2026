from __future__ import annotations

import pytest
from app import create_app


@pytest.fixture()
def app(tmp_path):
    app = create_app({
        'TESTING': True,
        'DATABASE_PATH': str(tmp_path / 'test.db'),
        'EXPORT_FOLDER': str(tmp_path / 'exports'),
        'LOG_FILE': str(tmp_path / 'app.log'),
    })
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()
