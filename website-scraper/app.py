from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from flask_cors import CORS

from config import Config
from database.database import get_configuration, get_job, get_jobs, get_stats, init_db
from routes.configuration_routes import configuration_bp
from routes.export_routes import export_bp
from routes.job_routes import job_bp
from routes.scraper_routes import scraper_bp
from auth import auth_bp, login_required


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    Path(app.config['EXPORT_FOLDER']).mkdir(parents=True, exist_ok=True)
    Path(app.config['LOG_FILE']).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config['DATABASE_PATH']).parent.mkdir(parents=True, exist_ok=True)

    CORS(app, resources={r'/api/*': {'origins': app.config['CORS_ORIGINS']}})
    configure_logging(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(scraper_bp)
    app.register_blueprint(job_bp)
    app.register_blueprint(configuration_bp)
    app.register_blueprint(export_bp)

    with app.app_context():
        init_db()

    @app.before_request
    def protect_application():
        public_paths = {'/login', '/health'}
        if request.path in public_paths or request.path.startswith('/static/'):
            return None
        if not session.get('user'):
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Login required.'}), 401
            return redirect(url_for('auth.login', next=request.full_path))
        return None

    @app.get('/')
    @login_required
    def dashboard():
        return render_template('dashboard.html', stats=get_stats(), jobs=get_jobs(limit=8))

    @app.get('/new-scraper')
    @login_required
    def new_scraper():
        configuration = None
        config_id = request.args.get('config', type=int)
        if config_id:
            configuration = get_configuration(config_id)
        return render_template('new_scraper.html', configuration=configuration)

    @app.get('/results/<int:job_id>')
    @login_required
    def results(job_id: int):
        return render_template('results.html', job=get_job(job_id), job_id=job_id)

    @app.get('/history')
    @login_required
    def history():
        return render_template('history.html', jobs=get_jobs(limit=250))

    @app.get('/configurations')
    @login_required
    def configurations_page():
        return render_template('configurations.html')

    @app.get('/exports')
    @login_required
    def exports_page():
        jobs = [job for job in get_jobs(limit=250) if job.get('records_extracted', 0) > 0]
        return render_template('exports.html', jobs=jobs)

    @app.get('/settings')
    @login_required
    def settings_page():
        return render_template('settings.html')

    @app.get('/help')
    @login_required
    def help_page():
        return render_template('help.html')

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    return app


def configure_logging(app: Flask) -> None:
    handler = RotatingFileHandler(
        app.config['LOG_FILE'], maxBytes=1_000_000, backupCount=3, encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s'
    ))
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', '5000')), debug=app.config['DEBUG'])
