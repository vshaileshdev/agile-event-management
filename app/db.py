import os
import sqlite3
from flask import g, current_app
import pymysql
import pymysql.cursors

class SQLiteWrapper:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, query, params=None):
        if params:
            query = query.replace('%s', '?')
            return self.conn.execute(query, params)
        return self.conn.execute(query)

    def cursor(self):
        return SQLiteCursorWrapper(self.conn.cursor())

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def rollback(self):
        self.conn.rollback()

class SQLiteCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        if params:
            query = query.replace('%s', '?')
            return self.cursor.execute(query, params)
        return self.cursor.execute(query)

    def fetchall(self):
        return self.cursor.fetchall()

    def fetchone(self):
        return self.cursor.fetchone()

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db_host = os.environ.get('DB_HOST')
        if db_host:
            # Connect to MySQL/RDS
            conn = pymysql.connect(
                host=db_host,
                port=int(os.environ.get('DB_PORT', 3306)),
                user=os.environ.get('DB_USER'),
                password=os.environ.get('DB_PASSWORD'),
                database=os.environ.get('DB_NAME'),
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False
            )
            class MySQLWrapper:
                def __init__(self, conn):
                    self.conn = conn
                def execute(self, query, params=None):
                    cursor = self.conn.cursor()
                    cursor.execute(query, params)
                    return cursor
                def cursor(self):
                    return self.conn.cursor()
                def commit(self):
                    self.conn.commit()
                def close(self):
                    self.conn.close()
                def rollback(self):
                    self.conn.rollback()
            db = g._database = MySQLWrapper(conn)
        else:
            # Fallback to local SQLite
            conn = sqlite3.connect(current_app.config['DATABASE'])
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            db = g._database = SQLiteWrapper(conn)
    return db

def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_app(app):
    app.teardown_appcontext(close_connection)
