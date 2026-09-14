import os
import sqlite3
from datetime import datetime

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

    empty = db.execute("SELECT COUNT(*) FROM works").fetchone()[0] == 0
    if empty:
        now = datetime.now().strftime("%d.%m %H:%M")
        db.executemany(
            "INSERT INTO works (title, type, description, content, created_by, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            [
                (
                    "Introduction to Programming",
                    "lecture",
                    "The very first lecture: what a program is, why Python.",
                    """Course: Programming Fundamentals.

A program is a sequence of instructions that a computer executes. We write programs in a
programming language such as Python, and the computer translates them into actions.

In this course you will learn how to think like a programmer: to break a problem into steps
and express each step precisely. Every lecture is followed by a practical work. Complete
every task to fix the material.""",
                    now,
                ),
                (
                    "Data Types and Variables",
                    "lecture",
                    "Integers, floating point numbers, strings and how to store values.",
                    """Data Types and Variables.

Any value we work with has a type: the kind of data it is and what operations are allowed
on it. The basic types in Python:

    int     - integer numbers: 5, -3, 0
    float   - real numbers: 3.14, -1.0, 2.5
    str     - text: "hello", "world"
    bool    - logical value: True, False

A variable is a named container that stores one value. Assignment binds a name to a value:

    x = 5
    name = "Ana"
    x = x + 1   # now x is 6

The type of a variable is not fixed: you may reassign it to a value of another type.""",
                    now,
                ),
                (
                    "Conditional Statements",
                    "lecture",
                    "if, elif, else and comparisons.",
                    """Conditional Statements.

Often a program must choose between several branches depending on a condition. Python uses
the keywords if, elif and else:

    if x > 0:
        print("positive")
    elif x == 0:
        print("zero")
    else:
        print("negative")

The condition is any expression that evaluates to a boolean. Useful comparisons:
>, <, >=, <=, ==, !=. You may combine them with and, or, not. Remember that the body of a
branch is indented by 4 spaces.""",
                    now,
                ),
                (
                    "Lab 1: Output",
                    "practical",
                    "First programs: printing text to the screen.",
                    "",
                    now,
                ),
                (
                    "Lab 2: Arithmetic",
                    "practical",
                    "Reading numbers and performing arithmetic operations.",
                    "",
                    now,
                ),
                (
                    "Lab 3: Conditions",
                    "practical",
                    "Branching: if, elif and else in practice.",
                    "",
                    now,
                ),
            ],
        )

        lab_ids = {r["title"]: r["id"] for r in db.execute("SELECT id, title FROM works WHERE type='practical'").fetchall()}

        db.executemany(
            "INSERT INTO tasks (work_id, title, statement, input_format, output_format, created_by) VALUES (?, ?, ?, ?, ?, 1)",
            [
                (
                    lab_ids["Lab 1: Output"],
                    "Hello, World!",
                    "Write a program that prints the classic greeting line.",
                    "There is no input in this problem.",
                    "Print a single line containing the text Hello, World!",
                ),
                (
                    lab_ids["Lab 1: Output"],
                    "Three Lines",
                    "Write a program that prints three lines: the word FIRST, then the word SECOND, then the word THIRD. Each word on its own line.",
                    "There is no input in this problem.",
                    "Print three lines: FIRST, SECOND, THIRD, one word per line.",
                ),
                (
                    lab_ids["Lab 2: Arithmetic"],
                    "Sum of Two Numbers",
                    "Given two integers, compute their sum.",
                    "The input contains two integers a and b separated by a single space. Their absolute value is not greater than 10^9.",
                    "Print a single integer: the sum a + b.",
                ),
                (
                    lab_ids["Lab 2: Arithmetic"],
                    "Product of Two Numbers",
                    "Given two integers, compute their product.",
                    "The input contains two integers a and b separated by a single space. Their absolute value is not greater than 10^9.",
                    "Print a single integer: the product a * b.",
                ),
                (
                    lab_ids["Lab 3: Conditions"],
                    "Even or Odd",
                    "Given an integer, determine whether it is even or odd.",
                    "The input contains a single integer n. Its absolute value is not greater than 10^9.",
                    "Print the word EVEN if the number is even, otherwise print the word ODD. Uppercase required.",
                ),
                (
                    lab_ids["Lab 3: Conditions"],
                    "Sign of an Integer",
                    "Given an integer, determine its sign.",
                    "The input contains a single integer n, different from 0. Its absolute value is not greater than 10^9.",
                    "Print the word POSITIVE if the number is positive, otherwise print the word NEGATIVE. Uppercase required.",
                ),
            ],
        )

        task_ids = {r["title"]: r["id"] for r in db.execute("SELECT id, title FROM tasks").fetchall()}

        lab_tests = [
            (task_ids["Hello, World!"], "", "Hello, World!"),
            (task_ids["Three Lines"], "", "FIRST\nSECOND\nTHIRD"),
            (task_ids["Sum of Two Numbers"], "2 3", "5"),
            (task_ids["Sum of Two Numbers"], "1000 1", "1001"),
            (task_ids["Sum of Two Numbers"], "-5 5", "0"),
            (task_ids["Product of Two Numbers"], "2 3", "6"),
            (task_ids["Product of Two Numbers"], "10 0", "0"),
            (task_ids["Product of Two Numbers"], "-4 7", "-28"),
            (task_ids["Even or Odd"], "42", "EVEN"),
            (task_ids["Even or Odd"], "7", "ODD"),
            (task_ids["Even or Odd"], "0", "EVEN"),
            (task_ids["Sign of an Integer"], "5", "POSITIVE"),
            (task_ids["Sign of an Integer"], "-9", "NEGATIVE"),
            (task_ids["Sign of an Integer"], "123456", "POSITIVE"),
        ]
        db.executemany(
            "INSERT INTO tests (task_id, input_data, output_data) VALUES (?, ?, ?)",
            lab_tests,
        )

    db.commit()
    db.close()