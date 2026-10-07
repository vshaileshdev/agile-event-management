# Database Architecture

## Engine
SQLite

## Tables

### users
Stores admin (and optionally standard) users.
- `user_id`: PK
- `name`: TEXT
- `email`: TEXT UNIQUE
- `password`: TEXT (Hashed)
- `role`: TEXT ('admin' or 'user')

### faculty_users
Stores faculty information.
- `faculty_id`: PK
- `employee_id`: TEXT UNIQUE
- `email`: TEXT UNIQUE

### event_tickets
Main event record.
- `event_id`: PK
- `faculty_id`: FK
- `event_name`, `venue_status`, `venue`, `participants`, `event_date`, `event_time`, `poster`, `status`

### event_guests
Guests linked to an event.
- `guest_id`: PK
- `event_id`: FK
- `guest_type`, `guest_name`, `designation`, `guest_phone`, `guest_address` (not in UI), `guest_house`, `guest_photo`, `guest_resume`

### event_replies
Admin replies. One per event.
- `reply_id`: PK
- `event_id`: FK (UNIQUE Constraint)
- `admin_id`: FK
- `reply_text`, `assigned_venue`, `status`
