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
        seed_works = [
            (
                "Introduction to Programming",
                "lecture",
                "The very first lecture: what a program is, why Python.",
                """Course: Programming Fundamentals.

A program is a sequence of instructions that a computer executes. We write programs in a
programming language such as Python, and the computer translates them into actions.

In this course you will learn how to think like a programmer: to break a problem into steps
and express each step precisely.

Each lecture is followed by a practical work. Complete it to fix the material.""",
            ),
            (
                "Data Types and Variables",
                "lecture",
                "Integers, floating point numbers, strings and how to store values.",
                """Data Types and Variables.

Any value we work with has a type: the kind of data it is and what operations are allowed
on it. The basic types in Python:

    int     - integer numbers: 5, -3, 0, 10**9
    float   - real numbers: 3.14, -1.0, 2.5e3
    str     - text: "hello", 'world'
    bool    - logical value: True, False

A variable is a named container that stores one value. Assignment binds a name to a value:

    x = 5
    name = "Ana"
    x = x + 1   # now x is 6

The type of a variable is not fixed: you may reassign it to a value of another type.""",
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
>, <, >=, <=, ==, !=. You may combine them with and, or, not.

Remember that the body of a branch is indented by 4 spaces.""",
            ),
            (
                "Lab 1: Hello, World!",
                "practical",
                "Write and run your first program.",
                """Statement.

Write a program that prints the line:

    Hello, World!

Input format.

There is no input in this problem.

Output format.

Print a single line containing the text Hello, World!.

Example.

Input:

(no input)

Output:

    Hello, World!""",
            ),
            (
                "Lab 2: Sum of Two Numbers",
                "practical",
                "Read two integers and print their sum.",
                """Statement.

Given two integers, print their sum.

Input format.

The first line contains two integers a and b, separated by a single space.
The numbers are not greater than 10^9 in absolute value.

Output format.

Print a single integer: the sum a + b.

Example.

Input:
    2 3

Output:
    5""",
            ),
            (
                "Lab 3: Even or Odd",
                "practical",
                "Check the parity of a number.",
                """Statement.

Given an integer, determine whether it is even or odd.

Input format.

The only line contains a single integer n, where |n| <= 10^9.

Output format.

Print the word EVEN if the number is even, otherwise print ODD. Uppercase required.

Example.

Input:
    42

Output:
    EVEN""",
            ),
        ]
        db.executemany(
            "INSERT INTO works (title, type, description, content, created_by, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            [(d[0], d[1], d[2], d[3], now) for d in seed_works],
        )

    db.commit()
    db.close()