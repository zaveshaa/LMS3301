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
                    "Введение в программирование",
                    "lecture",
                    "Первая лекция: что такое программа и зачем Python.",
                    """Курс: Основы программирования.

Программа — это последовательность инструкций, которые выполняет компьютер. Мы пишем
программы на языке программирования, например на Python, а компьютер переводит их
в действия.

В этом курсе вы научитесь мыслить как программист: разбивать задачу на шаги и чётко
формулировать каждый шаг. После каждой лекции идёт практическая работа. Выполняйте
все задачи, чтобы закрепить материал.""",
                    now,
                ),
                (
                    "Типы данных и переменные",
                    "lecture",
                    "Целые и вещественные числа, строки и хранение значений.",
                    """Типы данных и переменные.

Любое значение, с которым мы работаем, имеет тип: вид данных и список допустимых
операций. Основные типы в Python:

    int     - целые числа: 5, -3, 0
    float   - вещественные числа: 3.14, -1.0, 2.5
    str     - текст: "привет", "мир"
    bool    - логическое значение: True, False

Переменная — это именованный контейнер, который хранит значение. Присваивание
связывает имя со значением:

    x = 5
    name = "Аня"
    x = x + 1   # теперь x равно 6

Тип переменной не фиксирован: ей можно присвоить значение другого типа.""",
                    now,
                ),
                (
                    "Условные операторы",
                    "lecture",
                    "if, elif, else и операции сравнения.",
                    """Условные операторы.

Часто программа должна выбрать одну из нескольких ветвей в зависимости от условия.
В Python используются ключевые слова if, elif и else:

    if x > 0:
        print("положительное")
    elif x == 0:
        print("ноль")
    else:
        print("отрицательное")

Условие — это любое выражение, принимающее логическое значение. Полезные операции
сравнения: >, <, >=, <=, ==, !=. Их можно объединять с помощью and, or, not.
Помните, что тело ветки пишется с отступом в 4 пробела.""",
                    now,
                ),
                (
                    "Лабораторная 1: Вывод",
                    "practical",
                    "Первые программы: вывод текста на экран.",
                    "",
                    now,
                ),
                (
                    "Лабораторная 2: Арифметика",
                    "practical",
                    "Ввод чисел и арифметические операции.",
                    "",
                    now,
                ),
                (
                    "Лабораторная 3: Условия",
                    "practical",
                    "Ветвление: if, elif и else на практике.",
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
                    lab_ids["Лабораторная 1: Вывод"],
                    "Привет, мир!",
                    "Напишите программу, которая выводит классическую строку приветствия.",
                    "В этой задаче нет входных данных.",
                    "Выведите одну строку: Hello, World!",
                ),
                (
                    lab_ids["Лабораторная 1: Вывод"],
                    "Три строки",
                    "Напишите программу, которая выводит три строки: слово ПЕРВЫЙ, затем слово ВТОРОЙ, затем слово ТРЕТИЙ. Каждое слово — на отдельной строке.",
                    "В этой задаче нет входных данных.",
                    "Выведите три строки: ПЕРВЫЙ, ВТОРОЙ и ТРЕТИЙ, по одному слову в каждой строке.",
                ),
                (
                    lab_ids["Лабораторная 2: Арифметика"],
                    "Сумма двух чисел",
                    "Даны два целых числа, вычислите их сумму.",
                    "Входные данные содержат два целых числа a и b, разделённых одним пробелом. Их абсолютные значения не превышают 10^9.",
                    "Выведите одно целое число: сумму a + b.",
                ),
                (
                    lab_ids["Лабораторная 2: Арифметика"],
                    "Произведение двух чисел",
                    "Даны два целых числа, вычислите их произведение.",
                    "Входные данные содержат два целых числа a и b, разделённых одним пробелом. Их абсолютные значения не превышают 10^9.",
                    "Выведите одно целое число: произведение a * b.",
                ),
                (
                    lab_ids["Лабораторная 3: Условия"],
                    "Чётное или нечётное",
                    "Дано целое число, определите, является ли оно чётным или нечётным.",
                    "Входные данные содержат одно целое число n. Его абсолютное значение не превышает 10^9.",
                    "Выведите слово ЧЁТНОЕ, если число чётное, иначе выведите слово НЕЧЁТНОЕ.",
                ),
                (
                    lab_ids["Лабораторная 3: Условия"],
                    "Знак числа",
                    "Дано целое число, определите его знак.",
                    "Входные данные содержат одно целое число n, не равное нулю. Его абсолютное значение не превышает 10^9.",
                    "Выведите слово ПОЛОЖИТЕЛЬНОЕ, если число положительное, иначе выведите слово ОТРИЦАТЕЛЬНОЕ.",
                ),
            ],
        )

        task_ids = {r["title"]: r["id"] for r in db.execute("SELECT id, title FROM tasks").fetchall()}

        lab_tests = [
            (task_ids["Привет, мир!"], "", "Hello, World!"),
            (task_ids["Три строки"], "", "ПЕРВЫЙ\nВТОРОЙ\nТРЕТИЙ"),
            (task_ids["Сумма двух чисел"], "2 3", "5"),
            (task_ids["Сумма двух чисел"], "1000 1", "1001"),
            (task_ids["Сумма двух чисел"], "-5 5", "0"),
            (task_ids["Произведение двух чисел"], "2 3", "6"),
            (task_ids["Произведение двух чисел"], "10 0", "0"),
            (task_ids["Произведение двух чисел"], "-4 7", "-28"),
            (task_ids["Чётное или нечётное"], "42", "ЧЁТНОЕ"),
            (task_ids["Чётное или нечётное"], "7", "НЕЧЁТНОЕ"),
            (task_ids["Чётное или нечётное"], "0", "ЧЁТНОЕ"),
            (task_ids["Знак числа"], "5", "ПОЛОЖИТЕЛЬНОЕ"),
            (task_ids["Знак числа"], "-9", "ОТРИЦАТЕЛЬНОЕ"),
            (task_ids["Знак числа"], "123456", "ПОЛОЖИТЕЛЬНОЕ"),
        ]
        db.executemany(
            "INSERT INTO tests (task_id, input_data, output_data) VALUES (?, ?, ?)",
            lab_tests,
        )

    db.commit()
    db.close()