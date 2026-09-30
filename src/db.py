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
            full_name TEXT NOT NULL DEFAULT ''
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

        CREATE TABLE IF NOT EXISTS submission_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL REFERENCES submissions(id),
            test_id INTEGER NOT NULL REFERENCES tests(id),
            passed INTEGER NOT NULL DEFAULT 0,
            actual_output TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT ''
        );
        """
    )

    cols = {r["name"] for r in db.execute("PRAGMA table_info(users)").fetchall()}
    if "full_name" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN full_name TEXT NOT NULL DEFAULT ''")
    if "password_show" in cols:
        db.execute("ALTER TABLE users DROP COLUMN password_show")

    tcols = {r["name"] for r in db.execute("PRAGMA table_info(tasks)").fetchall()}
    if "score" in tcols:
        db.execute("ALTER TABLE tasks DROP COLUMN score")

    scols = {r["name"] for r in db.execute("PRAGMA table_info(submissions)").fetchall()}
    if "comment" not in scols:
        db.execute("ALTER TABLE submissions ADD COLUMN comment TEXT NOT NULL DEFAULT ''")

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

    if db.execute("SELECT COUNT(*) FROM works").fetchone()[0] == 0:
        _seed_demo(db)
    elif (
        db.execute("SELECT COUNT(*) FROM tasks WHERE title = 'Разворот числа'").fetchone()[0] == 0
        and db.execute("SELECT COUNT(*) FROM works WHERE title LIKE 'Практика%'").fetchone()[0] > 0
    ):
        _reset_demo(db)
        _seed_demo(db)

    db.commit()
    db.close()


def _reset_demo(db):
    db.execute("DELETE FROM submission_tests")
    db.execute("DELETE FROM submissions")
    db.execute("DELETE FROM work_groups")
    db.execute("DELETE FROM tests")
    db.execute("DELETE FROM tasks")
    db.execute("DELETE FROM works WHERE title LIKE 'Лекция%' OR title LIKE 'Практика%'")
    db.execute("DELETE FROM works WHERE type = 'lecture' OR type = 'practical'")


def _seed_demo(db):
    now = datetime.now().strftime("%d.%m %H:%M")

    def add_practical(title, description, tasks):
        cur = db.execute(
            "INSERT INTO works (title, type, description, content, created_at) VALUES (?, 'practical', ?, '', ?)",
            (title, description, now),
        )
        wid = cur.lastrowid
        for t in tasks:
            tcur = db.execute(
                "INSERT INTO tasks (work_id, title, statement, input_format, output_format) VALUES (?, ?, ?, ?, ?)",
                (wid, t["title"], t["statement"], t["input_format"], t["output_format"]),
            )
            tid = tcur.lastrowid
            for inp, out in t["tests"]:
                db.execute(
                    "INSERT INTO tests (task_id, input_data, output_data) VALUES (?, ?, ?)",
                    (tid, inp, out),
                )
        return wid

    def add_lecture(title, description, content):
        db.execute(
            "INSERT INTO works (title, type, description, content, created_at) VALUES (?, 'lecture', ?, ?, ?)",
            (title, description, content, now),
        )

    for p in PRACTICALS:
        add_practical(p["title"], p["description"], p["tasks"])
    for title, description, content in LECTURES:
        add_lecture(title, description, content)
    _seed_demo_submissions(db, now)


def _seed_demo_submissions(db, now):
    student = db.execute("SELECT id FROM users WHERE login = '5952_1'").fetchone()
    if student is None:
        return
    student_id = student["id"]

    def task_ids(title):
        rows = db.execute(
            "SELECT t.id FROM tasks t JOIN works w ON w.id = t.work_id "
            "WHERE w.type = 'practical' AND t.title = ? ORDER BY t.id",
            (title,),
        ).fetchall()
        return [r["id"] for r in rows]

    def tests_of(task_id):
        return [
            r["id"]
            for r in db.execute(
                "SELECT id FROM tests WHERE task_id = ? ORDER BY id", (task_id,)
            )
        ]

    def add_sub(task_id, code, status, comment, results):
        cur = db.execute(
            "INSERT INTO submissions (task_id, user_id, code, status, comment, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, student_id, code, status, comment, now),
        )
        sub_id = cur.lastrowid
        for test_id, (passed, actual, error) in zip(tests_of(task_id), results):
            db.execute(
                "INSERT INTO submission_tests (submission_id, test_id, passed, actual_output, error) VALUES (?, ?, ?, ?, ?)",
                (sub_id, test_id, 1 if passed else 0, actual, error),
            )

    sum_task = task_ids("Сумма цифр числа")
    parity_task = task_ids("Чётность числа")
    reverse_task = task_ids("Разворот числа")
    vowels_task = task_ids("Подсчёт гласных")

    if sum_task:
        add_sub(
            sum_task[0],
            "n = int(input())\ns = 0\nwhile n > 0:\n    s += 1\n    n //= 10\nprint(s)",
            "error",
            "Пройдено 2 из 6 тестов. Не пройден тест 1: Вывод не совпадает; вывод: 3",
            [
                (0, "3", "Вывод не совпадает"),
                (1, "0", ""),
                (0, "3", "Вывод не совпадает"),
                (0, "4", "Вывод не совпадает"),
                (0, "9", "Вывод не совпадает"),
                (1, "12", ""),
            ],
        )
        add_sub(
            sum_task[0],
            "print(sum(map(int, input())))",
            "ok",
            "Все 6 тестов пройдено",
            [(1, "", "")] * 6,
        )

    if parity_task:
        add_sub(
            parity_task[0],
            "n = int(input())\nprint('ЧЁТНОЕ' if n % 2 == 0 and n != 0 else 'НЕЧЁТНОЕ')",
            "error",
            "Пройдено 5 из 6 тестов. Не пройден тест 3: Вывод не совпадает; вывод: НЕЧЁТНОЕ",
            [
                (1, "ЧЁТНОЕ", ""),
                (1, "НЕЧЁТНОЕ", ""),
                (0, "НЕЧЁТНОЕ", "Вывод не совпадает"),
                (1, "НЕЧЁТНОЕ", ""),
                (1, "ЧЁТНОЕ", ""),
                (1, "НЕЧЁТНОЕ", ""),
            ],
        )

    if reverse_task:
        add_sub(
            reverse_task[0],
            "n = int(input())\nrev = 0\nwhile n > 0:\n    rev = rev * 10 + n % 10\nprint(rev)",
            "error",
            "Пройдено 0 из 5 тестов. Не пройден тест 1: Превышено время выполнения",
            [(0, "", "Превышено время выполнения")] * 5,
        )

    if vowels_task:
        add_sub(
            vowels_task[0],
            "word = input()\nvowels = 'аеёиоуыэюя'\ncount = sum(1 for c in word if c in vowels)\nprint(100 // (len(word) - count))",
            "error",
            "Пройдено 0 из 6 тестов. Не пройден тест 1: Ошибка выполнения: ZeroDivisionError: integer division or modulo by zero",
            [
                (0, "", "Ошибка выполнения: ZeroDivisionError: integer division or modulo by zero"),
                (0, "50", "Вывод не совпадает"),
                (0, "50", "Вывод не совпадает"),
                (0, "33", "Вывод не совпадает"),
                (0, "33", "Вывод не совпадает"),
                (0, "50", "Вывод не совпадает"),
            ],
        )


PRACTICALS = [
    {
        "title": "Практика: Арифметика",
        "description": "Вычисления, работа с целыми числами.",
        "tasks": [
            {
                "title": "Сумма цифр числа",
                "statement": "Дано целое неотрицательное число. Выведите сумму его цифр.\nНапример, для числа 123 сумма равна 1 + 2 + 3 = 6.",
                "input_format": "Одно целое неотрицательное число.",
                "output_format": "Одно целое число — сумма цифр.",
                "tests": [
                    ("123", "6"),
                    ("0", "0"),
                    ("999", "27"),
                    ("1000", "1"),
                    ("987654321", "45"),
                    ("111111111111", "12"),
                ],
            },
            {
                "title": "Чётность числа",
                "statement": "Дано целое число. Выведите «ЧЁТНОЕ», если оно чётное, и «НЕЧЁТНОЕ» в противном случае.\nНоль считается чётным числом.",
                "input_format": "Одно целое число.",
                "output_format": "«ЧЁТНОЕ» или «НЕЧЁТНОЕ».",
                "tests": [
                    ("4", "ЧЁТНОЕ"),
                    ("7", "НЕЧЁТНОЕ"),
                    ("0", "ЧЁТНОЕ"),
                    ("13", "НЕЧЁТНОЕ"),
                    ("100", "ЧЁТНОЕ"),
                    ("-3", "НЕЧЁТНОЕ"),
                ],
            },
            {
                "title": "Разворот числа",
                "statement": "Дано целое неотрицательное число. Выведите число, составленное из его цифр в обратном порядке.\nНапример, для числа 120 ответ — 21.",
                "input_format": "Одно целое неотрицательное число.",
                "output_format": "Одно целое число.",
                "tests": [
                    ("123", "321"),
                    ("120", "21"),
                    ("1000", "1"),
                    ("7", "7"),
                    ("9009", "9009"),
                ],
            },
            {
                "title": "Подсчёт гласных",
                "statement": "Дано слово из строчных русских букв. Подсчитайте, сколько в нём гласных букв.\nГласные: а, е, ё, и, о, у, ы, э, ю, я.",
                "input_format": "Одно слово.",
                "output_format": "Одно целое число — количество гласных.",
                "tests": [
                    ("аааа", "4"),
                    ("дом", "1"),
                    ("окно", "2"),
                    ("школа", "2"),
                    ("ключ", "1"),
                    ("сова", "2"),
                ],
            },
        ],
    },
]

LECTURES = [
    (
        "Лекция 1: Строки и работа с текстом",
        "Основы работы со строками в Python.",
        """Лекция 1. Строки и работа с текстом

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
- input().split() — стандартный способ чтения последовательности чисел.""",
    ),
    (
        "Лекция 2: Условные операторы",
        "Ветвления и логические выражения.",
        """Лекция 2. Условные операторы

1. Зачем нужны ветвления

Программа выполняет действия, используя данные. Иногда одно и то же действие нужно выполнить по-разному в зависимости от значения. Для этого используется if.

2. Простое условие

    age = 17
    if age >= 18:
        print('Совершеннолетний')

Если условие истинно — выполняется блок под if. Отступ в 4 пробела обязателен.

3. Ветка else

    age = 15
    if age >= 18:
        print('Совершеннолетний')
    else:
        print('Несовершеннолетний')

Выполнится ровно одна из веток.

4. Несколько условий: elif

    mark = 4
    if mark == 5:
        print('Отлично')
    elif mark == 4:
        print('Хорошо')
    else:
        print('Не отлично')

elif позволяет проверить несколько условий по очереди.

5. Операторы сравнения и логические

==   равно
!=   не равно
>    больше
<    меньше
and  и
or   или
not  не

    if x > 0 and x < 10:
        print('x в диапазоне от 1 до 9')

6. Вложенные условия

Условия можно вкладывать одно в другое:

    if a == b:
        if c > 0:
            print('случай 1')
        else:
            print('случай 2')

7. Хорошая привычка

Оформляйте условие так, чтобы в главной ветке был главный случай, а редкие — в else. Это делает код понятнее.""",
    ),
    (
        "Лекция 3: Циклы",
        "Повторение действий, for и while.",
        """Лекция 3. Циклы

1. Зачем нужны циклы

Цикл выполняет один и тот же блок кода несколько раз. Это избавляет от копирования кода.

2. Цикл for с range

    for i in range(5):
        print(i)

Выведет 0 1 2 3 4. range(5) — это последовательность от 0 до 4.

range(2, 10)   # от 2 до 9
    range(2, 10, 2)  # 2 4 6 8 — шаг 2

3. Накопление суммы

    total = 0
    for i in range(1, 6):
        total += i
    print(total)  # 15

Переменная total «копит» результат внутри цикла.

4. Обход списка

    nums = [3, 1, 4]
    for x in nums:
        print(x * 2)

5. Цикл while

while выполняется, пока условие истинно:

    n = 10
    while n > 0:
        print(n)
        n -= 1

Не забывайте менять переменную условия, иначе цикл не закончится.

6. break и continue

break — выйти из цикла сразу, continue — перейти к следующей итерации:

    for i in range(10):
        if i == 3:
            continue
        if i == 7:
            break
        print(i)

7. Что запомнить

- for нужен, когда известно количество повторений.
- while — когда повторяем, пока условие верно.
- += 1 — счётчик, += сумма — накопление.
- break и continue управляют ходом цикла.""",
    ),
    (
        "Лекция 4: Функции",
        "Создание функций, аргументы, return.",
        """Лекция 4. Функции

1. Зачем нужны функции

Функция — это именованный блок кода, который можно вызывать много раз. Это убирает повторение и делит задачу на части.

2. Простая функция

    def say_hello():
        print('Привет!')

    say_hello()
    say_hello()

3. Аргументы

    def sum2(a, b):
        print(a + b)

    sum2(3, 5)  # 8

4. return

Функция может вернуть результат командой return:

    def square(x):
        return x * x

    print(square(4))  # 16

После return выполнение функции заканчивается.

5. Значение по умолчанию

    def greet(name, greeting='Привет'):
        print(f'{greeting}, {name}!')

    greet('Аня')                 # Привет, Аня!
    greet('Аня', greeting='Здравствуйте')  # Здравствуйте, Аня!

6. Функции и входные данные

В задачах функции удобно использовать так: прочитать данные, вызвать функцию с данными, вывести результат.

    def digit_sum(x):
        s = 0
        while x > 0:
            s += x % 10
            x //= 10
        return s

    n = int(input())
    print(digit_sum(n))

7. Что запомнить

- def имя(аргументы): — объявление функции.
- return — вернуть результат.
- Имена функций пишут строчными буквами.
- Одна функция — одно понятное действие.""",
    ),
    (
        "Лекция 5: Списки",
        "Изменяемые последовательности, ввод массива.",
        """Лекция 5. Списки

1. Что такое список

Список — изменяемая упорядоченная последовательность элементов:

    nums = [10, 20, 30]
    words = ['один', 'два']

2. Индексы и срезы работают как у строк

    nums[0]     # 10
    nums[-1]    # 30
    nums[1:]    # [20, 30]
    nums[::-1]  # [30, 20, 10]

3. Стандартный ввод массива

Самая частая схема в задачах:

    n = int(input())
    a = list(map(int, input().split()))
    print(a)

input().split() режет строку на части, map(int, ...) превращает их в числа, list(...) собирает список.

4. Добавление и изменение

    a = [1, 2]
    a.append(3)   # [1, 2, 3]
    a[0] = 100    # [100, 2, 3]

5. Обход списка

    for x in a:
        print(x)

    for i in range(len(a)):
        print(i, a[i])

6. Полезные функции

len(a)    # длина
sum(a)    # сумма
max(a)    # максимум
min(a)    # минимум
sorted(a) # отсортированная копия

    data = [3, 1, 2]
    print(sum(data), max(data), sorted(data))  # 6 3 [1, 2, 3]

7. Что запомнить

- Списки изменяемы, строки — нет.
- input().split() + list(map(int, ...)) — стандартный ввод чисел.
- append добавляет элемент в конец.
- sum, max, min, sorted экономят код.""",
    ),
]