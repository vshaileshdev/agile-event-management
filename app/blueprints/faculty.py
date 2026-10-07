import os
import time
from flask import Blueprint, current_app, g, redirect, render_template, request, url_for, flash
from werkzeug.utils import secure_filename
from app.db import get_db
from app.blueprints.auth import login_required_faculty
import re

bp = Blueprint('faculty', __name__, url_prefix='/faculty')

@bp.route('/dashboard')
@login_required_faculty
def dashboard():
    db = get_db()
    events = db.execute(
        'SELECT * FROM event_tickets WHERE faculty_id = ? ORDER BY created_at DESC',
        (g.faculty['faculty_id'],)
    ).fetchall()
    return render_template('faculty/dashboard.html', events=events)

@bp.route('/event/new', methods=('GET', 'POST'))
@login_required_faculty
def raise_event():
    if request.method == 'POST':
        db = get_db()
        
        event_name = request.form.get('event_name')
        venue_status = request.form.get('venue_status')
        venue = request.form.get('venue') if venue_status == 'yes' else None
        participants = request.form.get('participants') if venue_status == 'no' else None
        event_date = request.form.get('event_date')
        event_time = request.form.get('event_time')
        
        error = None
        if not event_name or not venue_status or not event_date or not event_time:
            error = 'Missing required event fields.'
        elif venue_status == 'yes' and not venue:
            error = 'Venue is required when you have a venue.'
        elif venue_status == 'no' and not participants:
            error = 'Participants count is required when you need a venue.'
        
        poster_filename = None
        if 'poster' in request.files and request.files['poster'].filename != '':
            file = request.files['poster']
            poster_filename = f"{int(time.time())}_{secure_filename(file.filename)}"
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], poster_filename))
        
        if error is None:
            cursor = db.cursor()
            cursor.execute(
                '''INSERT INTO event_tickets 
                (faculty_id, event_name, venue_status, venue, participants, event_date, event_time, poster)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (g.faculty['faculty_id'], event_name, venue_status, venue, participants, event_date, event_time, poster_filename)
            )
            event_id = cursor.lastrowid
            
            guest_status = request.form.get('guest_status')
            if guest_status == 'yes':
                guest_count = int(request.form.get('guest_count', 0))
                for i in range(1, guest_count + 1):
                    g_type = request.form.get(f'guest_type_{i}')
                    g_name = request.form.get(f'guest_name_{i}')
                    g_designation = request.form.get(f'guest_designation_{i}')
                    g_phone = request.form.get(f'guest_phone_{i}')
                    
                    if not g_type or not g_name or not g_phone:
                        error = f'Missing required guest fields for guest {i} (type={g_type}, name={g_name}, phone={g_phone}).'
                        break
                    
                    if not re.match(r'^[6-9][0-9]{9}$', g_phone):
                        error = f'Invalid phone number for guest {i}.'
                        break
                    
                    g_house = request.form.get(f'guest_house_{i}') if g_type == 'external' else None
                    
                    photo_file = request.files.get(f'guest_photo_{i}')
                    photo_filename = None
                    if photo_file and photo_file.filename != '':
                        photo_filename = f"{int(time.time())}_photo_{i}_{secure_filename(photo_file.filename)}"
                        photo_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], photo_filename))
                        
                    resume_file = request.files.get(f'guest_resume_{i}')
                    resume_filename = None
                    if resume_file and resume_file.filename != '':
                        resume_filename = f"{int(time.time())}_resume_{i}_{secure_filename(resume_file.filename)}"
                        resume_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], resume_filename))
                    
                    cursor.execute(
                        '''INSERT INTO event_guests 
                        (event_id, guest_type, guest_name, designation, guest_phone, guest_house, guest_photo, guest_resume)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (event_id, g_type, g_name, g_designation, g_phone, g_house, photo_filename, resume_filename)
                    )
            
            if error is None:
                db.commit()
                return redirect(url_for('faculty.dashboard'))
            else:
                db.rollback()
        
        if error:
            flash(error)

    return render_template('faculty/raise_event.html')

@bp.route('/event/<int:id>')
@login_required_faculty
def view_event(id):
    db = get_db()
    event = db.execute(
        'SELECT * FROM event_tickets WHERE event_id = ? AND faculty_id = ?',
        (id, g.faculty['faculty_id'])
    ).fetchone()
    
    if not event:
        flash("Event not found.")
        return redirect(url_for('faculty.dashboard'))
        
    guests = db.execute(
        'SELECT * FROM event_guests WHERE event_id = ? ORDER BY guest_id ASC', (id,)
    ).fetchall()
    
    reply = db.execute(
        'SELECT * FROM event_replies WHERE event_id = ?', (id,)
    ).fetchone()
    
    return render_template('faculty/view_event.html', event=event, guests=guests, reply=reply)
