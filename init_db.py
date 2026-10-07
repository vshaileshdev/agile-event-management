import sqlite3
import os
from werkzeug.security import generate_password_hash
from app.app import create_app

def init_db():
    app = create_app()
    with app.app_context():
        DATABASE = app.config['DATABASE']
        conn = sqlite3.connect(DATABASE)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

    # Drop tables if they exist for clean initialization
    cursor.execute("DROP TABLE IF EXISTS event_replies")
    cursor.execute("DROP TABLE IF EXISTS event_guests")
    cursor.execute("DROP TABLE IF EXISTS event_tickets")
    cursor.execute("DROP TABLE IF EXISTS faculty_users")
    cursor.execute("DROP TABLE IF EXISTS users")

    # Create users table
    cursor.execute("""
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT CHECK( role IN ('user', 'admin') ) NOT NULL DEFAULT 'user',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create faculty_users table
    cursor.execute("""
        CREATE TABLE faculty_users (
            faculty_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE
        )
    """)

    # Create event_tickets table
    cursor.execute("""
        CREATE TABLE event_tickets (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id INTEGER NOT NULL,
            event_name TEXT NOT NULL,
            venue_status TEXT NOT NULL, 
            venue TEXT,
            participants INTEGER,
            event_date DATE NOT NULL,
            event_time TIME NOT NULL,
            poster TEXT,
            status TEXT DEFAULT 'Pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(faculty_id) REFERENCES faculty_users(faculty_id)
        )
    """)

    # Create event_guests table
    cursor.execute("""
        CREATE TABLE event_guests (
            guest_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            guest_type TEXT NOT NULL, 
            guest_name TEXT NOT NULL,
            designation TEXT,
            guest_phone TEXT NOT NULL,
            guest_address TEXT, 
            guest_house TEXT, 
            guest_photo TEXT,
            guest_resume TEXT,
            FOREIGN KEY(event_id) REFERENCES event_tickets(event_id)
        )
    """)

    # Create event_replies table
    cursor.execute("""
        CREATE TABLE event_replies (
            reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL UNIQUE,
            admin_id INTEGER NOT NULL,
            reply_text TEXT NOT NULL,
            assigned_venue TEXT,
            status TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(event_id) REFERENCES event_tickets(event_id),
            FOREIGN KEY(admin_id) REFERENCES users(user_id)
        )
    """)

    # Seed Admin User
    admin_password = generate_password_hash("admin123")
    cursor.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)", 
                   ("Admin User", "admin@vit.edu", admin_password, "admin"))

    # Seed Normal User (Optional as per instructions)
    student_password = generate_password_hash("student123")
    cursor.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)", 
                   ("Student User", "student@vit.edu", student_password, "user"))

    # Seed Faculty User
    cursor.execute("INSERT INTO faculty_users (employee_id, email) VALUES (?, ?)", 
                   ("emp123", "faculty@vit.edu"))

    conn.commit()
    conn.close()
    print("Database initialized and seeded successfully.")

if __name__ == '__main__':
    init_db()
