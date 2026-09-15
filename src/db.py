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
            role TEXT NOT NULL DEFAULT 'student',
            full_name TEXT NOT NULL DEFAULT '',
            password_show TEXT NOT NULL DEFAULT ''
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

        CREATE TABLE IF NOT EXISTS work_groups (
            work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
            group_name TEXT NOT NULL,
            PRIMARY KEY (work_id, group_name)
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES tasks(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            code TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        );
        """
    )

    cols = {r["name"] for r in db.execute("PRAGMA table_info(users)").fetchall()}
    if "full_name" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN full_name TEXT NOT NULL DEFAULT ''")
    if "password_show" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN password_show TEXT NOT NULL DEFAULT ''")

    seed_users = [
        ("admin", generate_password_hash("admin"), "admin"),
        ("5952_1", generate_password_hash("5952_1"), "student"),
    ]
    for login, pwd_hash, role in seed_users:
            exists = db.execute("SELECT id FROM users WHERE login = ?", (login,)).fetchone()
            if not exists:
                db.execute(
                    "INSERT INTO users (login, password_hash, role, password_show) VALUES (?, ?, ?, ?)",
                    (login, pwd_hash, role, login),
                )
            else:
                db.execute(
                    "UPDATE users SET password_show = ? WHERE login = ?",
                    (login, login),
                )

    if db.execute("SELECT COUNT(*) FROM works").fetchone()[0] == 0:
        _seed_demo(db)

    db.commit()
    db.close()


def _seed_demo(db):
    now = datetime.now().strftime("%d.%m %H:%M")

    cur = db.execute(
        "INSERT INTO works (title, type, description, content, created_at) VALUES (?, 'practical', ?, '', ?)",
        ("Практика: Массивы", "Одномерные массивы — ввод, обработка, вывод.", now),
    )
    work_id = cur.lastrowid

    tasks = [
        (
            "Сумма элементов массива",
            "Дано целое число N, а затем N целых чисел.\nНайдите сумму всех элементов массива.\nВыведите эту сумму как единственное целое число.",
            "Сначала вводится число N — количество элементов массива.\nЗатем через пробел вводятся N целых чисел.",
            "Одно целое число — сумма элементов массива.",
            [
                ("3\n1 2 3", "6"),
                ("5\n10 -5 0 7 3", "15"),
                ("1\n42", "42"),
                ("4\n-1 -2 -3 -4", "-10"),
            ],
        ),
        (
            "Максимальный элемент",
            "Дано целое число N, а затем N целых чисел.\nНайдите наибольший элемент массива и выведите его.",
            "Сначала вводится число N — количество элементов массива.\nЗатем через пробел вводятся N целых чисел.",
            "Одно целое число — наибольший элемент массива.",
            [
                ("4\n3 7 2 9", "9"),
                ("5\n-3 -1 -7 -2 -8", "-1"),
                ("3\n5 5 5", "5"),
                ("2\n100 -100", "100"),
            ],
        ),
    ]
    for title, statement, in_fmt, out_fmt, tests in tasks:
        tcur = db.execute(
            "INSERT INTO tasks (work_id, title, statement, input_format, output_format) VALUES (?, ?, ?, ?, ?)",
            (work_id, title, statement, in_fmt, out_fmt),
        )
        task_id = tcur.lastrowid
        for in_data, out_data in tests:
            db.execute(
                "INSERT INTO tests (task_id, input_data, output_data) VALUES (?, ?, ?)",
                (task_id, in_data, out_data),
            )

    lecture = """Лекция 1. Строки и работа с текстом

1. Что такое строка

Строка — это упорядоченная последовательность символов. В Python строки записываются в одинарных или двойных кавычках:

    name = 'Python'
    lang = "программирование"

Строка неизменяема: создать новую строку можно, а изменить уже существующую — нельзя. Любая операция со строкой возвращает новую строку.

st = 'привет'
st[0] = 'П'  # ошибка — так делать нельзя

2. Индексы и срезы

Каждый символ строки имеет свой индекс. Индексация начинается с нуля:

st = 'привет'
st[0]    # 'п'
st[-1]   # 'т'
st[1:4]  # 'рив'

Срезы позволяют выделять часть строки: st[start:stop:step]. Если параметр опущен, берётся граница строки.

word = 'abcdef'
word[::-1]  # 'fedcba' — разворот строки

3. Методы строк

Методы не меняют саму строку, а возвращают новую:

s = ' Привет, Мир! '

s.lower()       # 'привет, мир!' — все символы строчные
s.upper()       # 'ПРИВЕТ, МИР!' — все символы заглавные
s.strip()       # 'Привет, Мир!' — убирает пробелы по краям
s.replace('и', 'е')  # замена одного символа на другой
s.split(', ')   # ['Привет', 'Мир!'] — разрезает строку по разделителю
s.startswith('При')  # True — проверка начала строки

Метод split() особенно важен при решении задач на ввод данных. Его часто используют так:

data = input().split()
a, b, c = map(int, data)

4. Конкатенация и форматирование

Строки можно склеивать оператором + и умножать на число:

a = 'про'
b = 'грамм'
print(a + b + 'а')  # 'программа'
print('а' * 5)      # 'ааааа'

Для сборки строк с переменными удобно использовать f-строки:

name = 'Аня'
print(f'Привет, {name}!')  # 'Привет, Аня!'

5. Поиск подстроки

Оператор in проверяет, встречается ли подстрока в строке:

text = 'обучение программированию'
print('грамм' in text)  # True

Метод find() возвращает индекс первого вхождения или -1, если подстрока не найдена:

print(text.find('про'))  # 9

6. Символы и их порядки

Функции ord() и chr() переводят символ в его числовой код и обратно:

ord('A')   # 65
chr(65)    # 'A'

Это бывает полезно, когда нужно обработать текст посимвольно.

7. Что запомнить

- Строка неизменяема и индексируется с нуля.
- Срезы st[a:b] выделяют часть строки.
- Методы lower(), upper(), strip(), replace(), split() возвращают новые строки.
- f-строки — самый простой способ подставить значения в текст.
- input().split() — стандартный способ чтения последовательности чисел.

Практикуйтесь: перепишите все примеры в редакторе и посмотрите, как ведут себя методы на разных строках."""
    db.execute(
        "INSERT INTO works (title, type, description, content, created_at) VALUES (?, 'lecture', ?, ?, ?)",
        ("Лекция 1: Строки и работа с текстом", "Основы работы со строками в Python.", lecture, now),
    )