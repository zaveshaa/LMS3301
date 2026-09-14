import os
import sqlite3

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lms.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student'
        );

        CREATE TABLE IF NOT EXISTS works (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('lecture', 'practical')),
            description TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_id INTEGER NOT NULL REFERENCES works(id),
            title TEXT NOT NULL,
            statement TEXT NOT NULL DEFAULT '',
            input_format TEXT NOT NULL DEFAULT '',
            output_format TEXT NOT NULL DEFAULT '',
            created_by INTEGER REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES tasks(id),
            input_data TEXT NOT NULL,
            output_data TEXT NOT NULL
        );
        """
    )

    seed_users = [
        ("admin", generate_password_hash("admin"), "admin"),
        ("5952_1", generate_password_hash("5952_1"), "student"),
    ]
    for login, pwd_hash, role in seed_users:
        exists = db.execute("SELECT id FROM users WHERE login = ?", (login,)).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO users (login, password_hash, role) VALUES (?, ?, ?)",
                (login, pwd_hash, role),
            )

    db.commit()
    db.close()