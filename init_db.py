import os
import pymysql
import sqlite3
from werkzeug.security import generate_password_hash
from app.app import create_app

def init_db():
    app = create_app()
    with app.app_context():
        db_host = os.environ.get('DB_HOST')
        
        if db_host:
            conn = pymysql.connect(
                host=db_host,
                port=int(os.environ.get('DB_PORT', 3306)),
                user=os.environ.get('DB_USER'),
                password=os.environ.get('DB_PASSWORD'),
                database=os.environ.get('DB_NAME')
            )
            cursor = conn.cursor()
            autoincrement_syntax = "AUTO_INCREMENT"
        else:
            DATABASE = app.config['DATABASE']
            conn = sqlite3.connect(DATABASE)
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            autoincrement_syntax = "AUTOINCREMENT"

        # Drop tables if they exist for clean initialization
        cursor.execute("DROP TABLE IF EXISTS event_replies")
        cursor.execute("DROP TABLE IF EXISTS event_guests")
        cursor.execute("DROP TABLE IF EXISTS event_tickets")
        cursor.execute("DROP TABLE IF EXISTS faculty_users")
        cursor.execute("DROP TABLE IF EXISTS users")

        # Create users table
        cursor.execute(f"""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY {autoincrement_syntax},
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create faculty_users table
        cursor.execute(f"""
            CREATE TABLE faculty_users (
                faculty_id INTEGER PRIMARY KEY {autoincrement_syntax},
                employee_id VARCHAR(255) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE
            )
        """)

        # Create event_tickets table
        cursor.execute(f"""
            CREATE TABLE event_tickets (
                event_id INTEGER PRIMARY KEY {autoincrement_syntax},
                faculty_id INTEGER NOT NULL,
                event_name VARCHAR(255) NOT NULL,
                venue_status VARCHAR(50) NOT NULL, 
                venue VARCHAR(255),
                participants INTEGER,
                event_date DATE NOT NULL,
                event_time TIME NOT NULL,
                poster VARCHAR(255),
                status VARCHAR(50) DEFAULT 'Pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(faculty_id) REFERENCES faculty_users(faculty_id)
            )
        """)

        # Create event_guests table
        cursor.execute(f"""
            CREATE TABLE event_guests (
                guest_id INTEGER PRIMARY KEY {autoincrement_syntax},
                event_id INTEGER NOT NULL,
                guest_type VARCHAR(50) NOT NULL, 
                guest_name VARCHAR(255) NOT NULL,
                designation VARCHAR(255),
                guest_phone VARCHAR(50) NOT NULL,
                guest_address TEXT, 
                guest_house VARCHAR(255), 
                guest_photo VARCHAR(255),
                guest_resume VARCHAR(255),
                FOREIGN KEY(event_id) REFERENCES event_tickets(event_id)
            )
        """)

        # Create event_replies table
        cursor.execute(f"""
            CREATE TABLE event_replies (
                reply_id INTEGER PRIMARY KEY {autoincrement_syntax},
                event_id INTEGER NOT NULL UNIQUE,
                admin_id INTEGER NOT NULL,
                reply_text TEXT NOT NULL,
                assigned_venue VARCHAR(255),
                status VARCHAR(50) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(event_id) REFERENCES event_tickets(event_id),
                FOREIGN KEY(admin_id) REFERENCES users(user_id)
            )
        """)

        # Seed Admin User
        admin_password = generate_password_hash("admin123")
        placeholder = "%s" if db_host else "?"
        cursor.execute(f"INSERT INTO users (name, email, password, role) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})", 
                       ("Admin User", "admin@vit.edu", admin_password, "admin"))

        # Seed Normal User (Optional as per instructions)
        student_password = generate_password_hash("student123")
        cursor.execute(f"INSERT INTO users (name, email, password, role) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})", 
                       ("Student User", "student@vit.edu", student_password, "user"))

        # Seed Faculty User
        cursor.execute(f"INSERT INTO faculty_users (employee_id, email) VALUES ({placeholder}, {placeholder})", 
                       ("emp123", "faculty@vit.edu"))

        conn.commit()
        conn.close()
        print("Database initialized and seeded successfully.")

if __name__ == '__main__':
    init_db()
