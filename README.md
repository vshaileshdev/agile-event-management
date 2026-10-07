# Event Management Testing

A Flask-based reimplementation of the Event Management System designed for software testing and Selenium automation.

## Prerequisites
- Python 3.9+
- Chrome browser (for Selenium tests)

## Installation
1. Create virtual environment: `python -m venv venv`
2. Activate it: `.\venv\Scripts\Activate.ps1` (Windows)
3. Install dependencies: `pip install -r requirements.txt`

## Database Setup
Run the initialization script to create tables and seed default users:
`python init_db.py`

### Seed Credentials
- **Admin**: `admin@vit.edu` / `admin123`
- **Faculty**: `emp123` / `faculty@vit.edu`

## Running the Application
`python -m flask --app app.app run`
The app will be available at `http://127.0.0.1:5000`

## Running Tests
Execute all 21 Selenium and pytest tests using:
`pytest -v tests/`

Test output will demonstrate full End-to-End coverage including event creation, authentication permutations, guest management logic, edge cases, admin processing, and database constraints.
