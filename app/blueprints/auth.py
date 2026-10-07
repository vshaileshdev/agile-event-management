import functools
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from app.db import get_db

bp = Blueprint('auth', __name__)

@bp.route('/login/faculty', methods=('GET', 'POST'))
def login_faculty():
    if request.method == 'POST':
        employee_id = request.form['employee_id']
        email = request.form['email']
        db = get_db()
        error = None

        faculty = db.execute(
            'SELECT * FROM faculty_users WHERE employee_id = ? AND email = ?', (employee_id, email)
        ).fetchone()

        if faculty is None:
            error = 'Invalid Employee ID or Email.'

        if error is None:
            session.clear()
            session['faculty_id'] = faculty['faculty_id']
            session['role'] = 'faculty'
            return redirect(url_for('faculty.dashboard'))

        flash(error)

    return render_template('auth/login_faculty.html')

@bp.route('/login/admin', methods=('GET', 'POST'))
def login_admin():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        error = None

        admin = db.execute(
            "SELECT * FROM users WHERE email = ? AND role = 'admin'",
            (email,)
        ).fetchone()

        if admin is None:
            error = 'Invalid Admin Email.'
        elif not check_password_hash(admin['password'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = admin['user_id']
            session['role'] = 'admin'
            return redirect(url_for('admin.dashboard'))

        flash(error)

    return render_template('auth/login_admin.html')

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login_faculty'))

def login_required_faculty(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.faculty is None:
            return redirect(url_for('auth.login_faculty'))
        return view(**kwargs)
    return wrapped_view

def login_required_admin(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.admin is None:
            return redirect(url_for('auth.login_admin'))
        return view(**kwargs)
    return wrapped_view

@bp.before_app_request
def load_logged_in_user():
    role = session.get('role')
    
    if role == 'faculty':
        faculty_id = session.get('faculty_id')
        g.faculty = get_db().execute(
            'SELECT * FROM faculty_users WHERE faculty_id = ?', (faculty_id,)
        ).fetchone()
        g.admin = None
    elif role == 'admin':
        user_id = session.get('user_id')
        g.admin = get_db().execute(
            'SELECT * FROM users WHERE user_id = ?', (user_id,)
        ).fetchone()
        g.faculty = None
    else:
        g.faculty = None
        g.admin = None
