from __future__ import annotations
from functools import wraps
from flask import Blueprint, current_app, redirect, render_template, request, session, url_for, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('user'):
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Login required.'}), 401
            return redirect(url_for('auth.login', next=request.full_path))
        return view(*args, **kwargs)
    return wrapped

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        expected_user = current_app.config['ADMIN_USERNAME']
        password_hash = current_app.config['ADMIN_PASSWORD_HASH']
        if username == expected_user and check_password_hash(password_hash, password):
            session.clear(); session['user'] = username
            return redirect(request.args.get('next') or url_for('dashboard'))
        error = 'Invalid username or password.'
    return render_template('login.html', error=error)

@auth_bp.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

def default_password_hash() -> str:
    return generate_password_hash('Admin@123')
