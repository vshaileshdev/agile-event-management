from flask import Blueprint, g, redirect, render_template, request, url_for, flash
from app.db import get_db
from app.blueprints.auth import login_required_admin

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/dashboard')
@login_required_admin
def dashboard():
    db = get_db()
    events = db.execute(
        '''SELECT e.*, f.employee_id 
           FROM event_tickets e 
           JOIN faculty_users f ON e.faculty_id = f.faculty_id
           ORDER BY e.created_at DESC'''
    ).fetchall()
    return render_template('admin/dashboard.html', events=events)

@bp.route('/event/<int:id>')
@login_required_admin
def view_event(id):
    db = get_db()
    event = db.execute(
        '''SELECT e.*, f.employee_id 
           FROM event_tickets e 
           JOIN faculty_users f ON e.faculty_id = f.faculty_id
           WHERE e.event_id = %s''', (id,)
    ).fetchone()
    
    if not event:
        flash("Event not found.")
        return redirect(url_for('admin.dashboard'))
        
    guests = db.execute(
        'SELECT * FROM event_guests WHERE event_id = %s ORDER BY guest_id ASC', (id,)
    ).fetchall()
    
    reply = db.execute(
        'SELECT * FROM event_replies WHERE event_id = %s', (id,)
    ).fetchone()
    
    return render_template('admin/view_event.html', event=event, guests=guests, reply=reply)

@bp.route('/event/<int:id>/reply', methods=('GET', 'POST'))
@login_required_admin
def reply_event(id):
    db = get_db()
    event = db.execute(
        'SELECT * FROM event_tickets WHERE event_id = %s', (id,)
    ).fetchone()
    
    if not event:
        flash("Event not found.")
        return redirect(url_for('admin.dashboard'))
        
    guests = db.execute(
        'SELECT * FROM event_guests WHERE event_id = %s ORDER BY guest_id ASC', (id,)
    ).fetchall()
    
    reply = db.execute(
        'SELECT * FROM event_replies WHERE event_id = %s', (id,)
    ).fetchone()
    
    if request.method == 'POST':
        status = request.form.get('status')
        reply_text = request.form.get('reply_text')
        assigned_venue = request.form.get('assigned_venue')
        
        cursor = db.cursor()
        
        if reply:
            cursor.execute(
                '''UPDATE event_replies 
                   SET reply_text = %s, assigned_venue = %s, status = %s
                   WHERE event_id = %s''',
                (reply_text, assigned_venue, status, id)
            )
        else:
            cursor.execute(
                '''INSERT INTO event_replies 
                   (event_id, admin_id, reply_text, assigned_venue, status)
                   VALUES (%s, %s, %s, %s, %s)''',
                (id, g.admin['user_id'], reply_text, assigned_venue, status)
            )
            
        cursor.execute(
            'UPDATE event_tickets SET status = %s WHERE event_id = %s',
            (status, id)
        )
        
        db.commit()
        return redirect(url_for('admin.view_event', id=id))

    return render_template('admin/reply_event.html', event=event, guests=guests, reply=reply)
