# Event Management Testing - Architecture & Implementation Plan

## 1. Reference Feature Inventory
- **Faculty Login:** Employee ID + Institutional Email (no password).
- **Admin Login:** Email + Password.
- **Event Creation (Faculty):**
  - Event Name, Date, Time, Poster (optional).
  - Venue Preference: "Have Venue" (specify venue) vs "Need Venue" (specify expected participants).
  - Dynamic Guests: Toggle for Yes/No. If Yes, allows dynamic creation of N guests.
    - Fields: Type (Internal/External), Name, Designation (optional), Phone (10 digits starting with 6-9), Guest House (Yes/No, External only), Photo (optional), Resume (optional).
- **Event Dashboard (Faculty & Admin):** View raised events.
- **Admin Event Processing:**
  - View event details and guests.
  - Submit exactly one reply per event (status, assigned venue, text).
  - Update existing reply if the admin replies again.
- **Faculty View Reply:** Faculty can see the admin's reply and status update.

## 2. Existing Workflow Analysis
- **Roles:** Admin (in `users` table), Faculty (in `faculty_users` table).
- **Events:** Faculty raises an event (creates `event_tickets` record) and optional guests (creates `event_guests` records).
- **Replies:** Admin reviews the event, creates/updates the single `event_replies` record, which strictly updates the `status` of the `event_tickets` record.

## 3. Proposed Flask Architecture
- Application uses Flask with blueprints for modularity (`auth`, `faculty`, `admin`).
- Flask-Session or simple signed cookie sessions for authentication.
- Jinja2 templates for HTML rendering, maintaining the original UI classes and structure.
- Werkzeug for secure file uploads to a local `uploads` directory.
- Raw SQLite3 with parameterized queries (no ORM).
- **No changes will be made to `reference/`**. It remains entirely read-only. This is a clean reimplementation in Python/Flask, not a line-by-line conversion.

## 4. Proposed Folder Structure
```text
EventManagementTesting/
├── app/
│   ├── app.py                  # Main Flask application
│   ├── db.py                   # SQLite database connection setup
│   ├── blueprints/             # Flask Blueprints
│   │   ├── auth.py             # Login/Logout logic
│   │   ├── faculty.py          # Faculty specific routes
│   │   └── admin.py            # Admin specific routes
│   ├── templates/              # HTML templates (mimicking original UI)
│   │   ├── base.html
│   │   ├── auth/login.html
│   │   ├── faculty/dashboard.html
│   │   ├── faculty/raise_event.html
│   │   ├── admin/dashboard.html
│   │   └── admin/reply_event.html
│   ├── static/
│   │   ├── css/style.css       # Original CSS
│   │   └── js/main.js          # Minimal JS (e.g. dynamic guests)
│   └── uploads/                # For posters, photos, resumes
├── tests/
│   ├── conftest.py             # pytest fixtures (db setup, flask app, selenium webdriver, credentials)
│   ├── test_auth.py            # Login tests
│   ├── test_faculty.py         # Faculty actions tests (event creation)
│   ├── test_admin.py           # Admin actions tests (reply)
│   └── test_e2e.py             # Full End-to-End test
├── docs/
│   ├── architecture.md
│   ├── test_plan.md
│   ├── test_cases.md
│   ├── selenium_strategy.md
│   └── database.md
├── reference/                  # Read-only reference
└── README.md
```

## 5. SQLite Schema
```sql
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role TEXT CHECK( role IN ('user', 'admin') ) NOT NULL DEFAULT 'user',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE faculty_users (
    faculty_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE
);

CREATE TABLE event_tickets (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER NOT NULL,
    event_name TEXT NOT NULL,
    venue_status TEXT NOT NULL, -- 'yes' or 'no'
    venue TEXT,
    participants INTEGER,
    event_date DATE NOT NULL,
    event_time TIME NOT NULL,
    poster TEXT,
    status TEXT DEFAULT 'Pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(faculty_id) REFERENCES faculty_users(faculty_id)
);

CREATE TABLE event_guests (
    guest_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    guest_type TEXT NOT NULL, -- 'internal' or 'external'
    guest_name TEXT NOT NULL,
    designation TEXT,
    guest_phone TEXT NOT NULL,
    guest_address TEXT, -- Maintained for DB extensibility, NOT shown in UI
    guest_house TEXT, -- 'yes', 'no' or NULL
    guest_photo TEXT,
    guest_resume TEXT,
    FOREIGN KEY(event_id) REFERENCES event_tickets(event_id)
);

CREATE TABLE event_replies (
    reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL UNIQUE, -- Enforces exactly one reply per event
    admin_id INTEGER NOT NULL,
    reply_text TEXT NOT NULL,
    assigned_venue TEXT,
    status TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(event_id) REFERENCES event_tickets(event_id),
    FOREIGN KEY(admin_id) REFERENCES users(user_id)
);
```
*Note: `guest_address` exists in the schema for future use but will not be rendered or captured in the UI.*

## 6. Route/Page Map
- `/login/admin`: Admin login.
- `/login/faculty`: Faculty login.
- `/logout`: Clears session.
- `/faculty/dashboard`: Lists events by this faculty.
- `/faculty/event/new`: Form to raise event.
- `/faculty/event/<id>`: View specific event and its reply.
- `/admin/dashboard`: Lists all events.
- `/admin/event/<id>`: View specific event and guests.
- `/admin/event/<id>/reply`: Reply form.

## 7. Authentication/Session Design
- **Faculty Authentication:** Intentionally passwordless, verifying only `employee_id` and `email` against the `faculty_users` table to maintain reference workflow.
- **Admin Authentication:** Standard email + hashed password using `werkzeug.security`.

## 8. Event Creation Workflow (UI Fidelity)
- **Venue Preference:** Selecting "Have Venue" shows the venue field. Selecting "Need Venue" shows expected participants.
- **Guests Present:** Selecting "No" hides all guest sections. Selecting "Yes" requests a count and dynamically generates sections.
- **Display logic:** If a designation is omitted, "Not Provided" is shown in views. If a photo/resume is omitted, no broken image link or file tag is rendered.

## 9. Dynamic Guest Form Design & Selenium Testability
- Instead of PHP-style array parameters (`name="guest_name[]"`), the frontend will use deterministic, indexed IDs and names.
- Example structure for Guest 1:
  - Container: `id="guest-section-1"`, `data-testid="guest-section-1"`
  - Type: `name="guest_type_1"`, `id="guest-type-1"`
  - Name: `name="guest_name_1"`, `id="guest-name-1"`
  - Designation: `name="guest_designation_1"`, `id="guest-designation-1"`
  - Phone: `name="guest_phone_1"`, `id="guest-phone-1"`
  - Guest House: `name="guest_house_1"`, `id="guest-house-1"`
  - Photo: `name="guest_photo_1"`, `id="guest-photo-1"`
  - Resume: `name="guest_resume_1"`, `id="guest-resume-1"`
- The Flask backend will extract the total `guest_count` submitted by the form and loop from `1` to `N` to safely extract fields (e.g., `request.form.get(f'guest_type_{i}')`), reconstructing the records deterministically.

## 10. File Upload Design
- `werkzeug.utils.secure_filename` to sanitize.
- Files stored locally in `app/static/uploads` to allow simple and secure serving by Flask.

## 11. Admin Reply Logic
- Fetches event.
- **Strict One-Reply Rule:** Checks if a reply exists.
  - If a reply exists for `event_id`, it is UPDATED via `UPDATE`.
  - If no reply exists, it is CREATED via `INSERT`.
- Simultaneously updates `status` in the `event_tickets` table to match.
- Never creates a second row in `event_replies` for the same event.

## 12. Test Data Strategy
- `init_db.py` will generate the tables and seed accounts.
- Seed credentials for automated tests will be stored explicitly in a central testing configuration file (like `tests/conftest.py`) so test files never duplicate credentials.

## 13. Recommended Implementation Order
1. Setup virtual environment, install requirements.
2. Build DB schema and seeding script (`app/db.py`).
3. Build Flask app skeleton and authentication blueprint (`app/blueprints/auth.py`).
4. Build Faculty Event Creation UI and logic with deterministic indexing (`app/blueprints/faculty.py`).
5. Build Admin UI and one-reply logic (`app/blueprints/admin.py`).
6. Create supporting documentation (`docs/`).
7. Write Selenium fixtures and basic test cases (`tests/`).
8. Implement end-to-end test and refine test reporting.
