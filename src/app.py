import os
import re
import secrets
import string
from datetime import datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db, init_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = "pytestlms-dev-secret-key"

ROLE_LABELS = {"admin": "Преподаватель", "student": "Студент"}
TYPE_LABELS = {"lecture": "Лекция", "practical": "Практика"}
STATUS_LABELS = {"pending": "На проверке", "ok": "Зачтено", "error": "Не зачтено"}


def get_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    db.close()
    return user


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_user()
            if user is None:
                return redirect(url_for("login"))
            if user["role"] != "admin" and user["role"] not in roles:
                return redirect(url_for("home"))
            return f(*args, **kwargs)

        return wrapper

    return decorator


@app.context_processor
def inject_user():
    user = get_user()
    return {
        "current_login": user["login"] if user else None,
        "current_role": user["role"] if user else None,
        "role_label": ROLE_LABELS.get(user["role"], user["role"]) if user else None,
        "type_label": TYPE_LABELS,
        "status_label": STATUS_LABELS,
    }


def get_group(login):
    if login and "_" in login:
        return login.split("_")[0]
    return None


def generate_password():
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def parse_bulk_tests(text):
    blocks = re.split(r"(?m)^\s*-{3}\s*$", text)
    tests = []
    for i, block in enumerate(blocks, 1):
        block = block.strip("\n").strip()
        if not block:
            continue
        lines = block.splitlines()
        in_lines, out_lines, mode, found_out = [], [], None, False
        for ln in lines:
            low = ln.strip().lower()
            if low.startswith("ввод:") or low.startswith("input:"):
                mode = "in"
                continue
            if low.startswith("вывод:") or low.startswith("output:"):
                mode = "out"
                found_out = True
                continue
            if mode == "out":
                out_lines.append(ln)
            else:
                in_lines.append(ln)
        if not found_out:
            raise ValueError(f"В блоке {i} нет строки «Вывод:»")
        out = "\n".join(out_lines).strip()
        if not out:
            raise ValueError(f"Блок {i}: пустой ожидаемый вывод")
        tests.append(("\n".join(in_lines).strip(), out))
    return tests


def all_group_names(db):
    return [
        r[0]
        for r in db.execute(
            "SELECT DISTINCT substr(login, 1, instr(login, '_') - 1) AS g FROM users WHERE role='student' AND login LIKE '%\\_%' ESCAPE '\\' ORDER BY g"
        )
    ]


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_val = request.form["login"].strip()
        password = request.form["password"]
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE login = ?", (login_val,)).fetchone()
        db.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("home"))
        flash("Неверный логин или пароль", "error")
    return render_template("login.html")


@app.route("/home")
@login_required
def home():
    user = get_user()
    if user["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("student_cabinet"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- student

@app.route("/student")
@login_required
@role_required("student")
def student_cabinet():
    user = get_user()
    group = get_group(user["login"])
    db = get_db()
    if group:
        works = db.execute(
            """
            SELECT w.*, (SELECT COUNT(*) FROM tasks t WHERE t.work_id = w.id) AS task_count
            FROM works w
            WHERE NOT EXISTS (SELECT 1 FROM work_groups WHERE work_groups.work_id = w.id)
               OR EXISTS (SELECT 1 FROM work_groups
                          WHERE work_groups.work_id = w.id AND work_groups.group_name = ?)
            ORDER BY w.type, w.id
            """,
            (group,),
        ).fetchall()
    else:
        works = db.execute(
            """
            SELECT w.*, (SELECT COUNT(*) FROM tasks t WHERE t.work_id = w.id) AS task_count
            FROM works w ORDER BY w.type, w.id
            """
        ).fetchall()
    db.close()
    return render_template("cabinet.html", works=works)


@app.route("/student/works/<int:work_id>")
@login_required
@role_required("student")
def student_work(work_id):
    db = get_db()
    work = db.execute("SELECT * FROM works WHERE id = ?", (work_id,)).fetchone()
    if work is None:
        flash("Работа не найдена", "error")
        return redirect(url_for("student_cabinet"))
    tasks = db.execute("SELECT * FROM tasks WHERE work_id = ?", (work_id,)).fetchall()
    db.close()
    return render_template("work_detail.html", work=work, tasks=tasks)


@app.route("/student/works/<int:work_id>/tasks/<int:task_id>")
@login_required
@role_required("student")
def student_task(work_id, task_id):
    db = get_db()
    work = db.execute("SELECT * FROM works WHERE id = ?", (work_id,)).fetchone()
    task = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND work_id = ?", (task_id, work_id)
    ).fetchone()
    if work is None or task is None:
        flash("Задача не найдена", "error")
        return redirect(url_for("student_cabinet"))
    tests = db.execute("SELECT * FROM tests WHERE task_id = ?", (task_id,)).fetchall()
    submission = db.execute(
        "SELECT * FROM submissions WHERE task_id = ? AND user_id = ? ORDER BY id DESC LIMIT 1",
        (task_id, get_user()["id"]),
    ).fetchone()
    attempt_count = db.execute(
        "SELECT COUNT(*) FROM submissions WHERE task_id = ? AND user_id = ?",
        (task_id, get_user()["id"]),
    ).fetchone()[0]
    db.close()
    return render_template(
        "task_detail.html",
        work=work,
        task=task,
        tests=tests,
        submission=submission,
        attempt_count=attempt_count,
    )


@app.route("/student/works/<int:work_id>/tasks/<int:task_id>/submit", methods=["POST"])
@login_required
@role_required("student")
def student_submit(work_id, task_id):
    db = get_db()
    work = db.execute("SELECT id FROM works WHERE id = ?", (work_id,)).fetchone()
    task = db.execute("SELECT id FROM tasks WHERE id = ? AND work_id = ?", (task_id, work_id)).fetchone()
    if work is None or task is None:
        db.close()
        flash("Задача не найдена", "error")
        return redirect(url_for("student_cabinet"))
    code = request.form.get("code", "")
    if not code.strip():
        flash("Напишите код, прежде чем отправлять на проверку", "error")
        db.close()
        return redirect(url_for("student_task", work_id=work_id, task_id=task_id))
    db.execute(
        "INSERT INTO submissions (task_id, user_id, code, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
        (task_id, get_user()["id"], code, datetime.now().strftime("%d.%m %H:%M")),
    )
    db.commit()
    db.close()
    flash("Решение отправлено на проверку", "success")
    return redirect(url_for("student_task", work_id=work_id, task_id=task_id))


# ---------------------------------------------------------------- admin

@app.route("/admin")
@login_required
@role_required("admin")
def admin_dashboard():
    db = get_db()
    student_count = db.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0]
    work_count = db.execute("SELECT COUNT(*) FROM works").fetchone()[0]
    task_count = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]

    student_rows = db.execute("SELECT * FROM users WHERE role = 'student' ORDER BY login").fetchall()
    student_groups = {}
    for s in student_rows:
        student_groups.setdefault(get_group(s["login"]) or "—", []).append(s)
    groups = all_group_names(db)

    works = []
    for w in db.execute("SELECT * FROM works ORDER BY type, id"):
        tasks = []
        for t in db.execute("SELECT * FROM tasks WHERE work_id = ? ORDER BY id", (w["id"],)).fetchall():
            tests = db.execute("SELECT * FROM tests WHERE task_id = ? ORDER BY id", (t["id"],)).fetchall()
            tasks.append({"task": t, "tests": tests})
        wgroups = [
            r["group_name"]
            for r in db.execute("SELECT group_name FROM work_groups WHERE work_id = ?", (w["id"],))
        ]
        works.append({"work": w, "tasks": tasks, "groups": wgroups})
    db.close()

    return render_template(
        "admin_panel.html",
        works=works,
        student_groups=student_groups,
        groups=groups,
        student_count=student_count,
        work_count=work_count,
        task_count=task_count,
        group_count=len(groups),
    )


def admin_url(fragment):
    return url_for("admin_dashboard", _anchor=fragment)


# --- работы

@app.route("/admin/works")
@login_required
@role_required("admin")
def admin_works():
    return redirect(admin_url("works"))


@app.route("/admin/works/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_work_new():
    if request.method == "POST":
        title = request.form["title"].strip()
        wtype = request.form["type"]
        description = request.form["description"].strip()
        content = request.form["content"].strip()
        if not title:
            flash("Укажите название работы")
        else:
            db = get_db()
            db.execute(
                "INSERT INTO works (title, type, description, content, created_by, created_at) VALUES (?, ?, ?, ?, 1, ?)",
                (title, wtype, description, content, datetime.now().strftime("%d.%m %H:%M")),
            )
            db.commit()
            work_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.close()
            return redirect(admin_url(f"work-{work_id}"))
    return redirect(admin_url("works"))


@app.route("/admin/works/<int:work_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_work_detail(work_id):
    if request.method == "GET":
        return redirect(admin_url(f"work-{work_id}"))
    db = get_db()
    work = db.execute("SELECT * FROM works WHERE id = ?", (work_id,)).fetchone()
    if work is None:
        db.close()
        flash("Работа не найдена", "error")
        return redirect(admin_url("works"))
    action = request.form.get("action")
    if action == "edit":
        title = request.form["title"].strip()
        wtype = request.form["type"]
        description = request.form["description"].strip()
        content = request.form["content"].strip()
        if not title:
            flash("Укажите название работы")
        else:
            db.execute(
                "UPDATE works SET title = ?, type = ?, description = ?, content = ? WHERE id = ?",
                (title, wtype, description, content, work_id),
            )
            db.commit()
    elif action == "groups":
        db.execute("DELETE FROM work_groups WHERE work_id = ?", (work_id,))
        for g in request.form.getlist("groups"):
            if g.strip():
                db.execute(
                    "INSERT INTO work_groups (work_id, group_name) VALUES (?, ?)",
                    (work_id, g.strip()),
                )
        db.commit()
    db.close()
    return redirect(admin_url(f"work-{work_id}"))


@app.route("/admin/works/<int:work_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def admin_work_delete(work_id):
    db = get_db()
    db.execute("DELETE FROM works WHERE id = ?", (work_id,))
    db.commit()
    db.close()
    flash("Работа удалена", "success")
    return redirect(admin_url("works"))


# --- задачи

@app.route("/admin/works/<int:work_id>/tasks/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_task_new(work_id):
    if request.method == "POST":
        title = request.form["title"].strip()
        statement = request.form["statement"].strip()
        input_format = request.form.get("input_format", "").strip()
        output_format = request.form.get("output_format", "").strip()
        if not title:
            flash("Укажите название задачи")
        else:
            db = get_db()
            db.execute(
                "INSERT INTO tasks (work_id, title, statement, input_format, output_format, created_by) VALUES (?, ?, ?, ?, ?, 1)",
                (work_id, title, statement, input_format, output_format),
            )
            db.commit()
            task_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.close()
            return redirect(admin_url(f"work-{work_id}task-{task_id}"))
    return redirect(admin_url(f"work-{work_id}"))


@app.route("/admin/tasks/<int:task_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_task_edit(task_id):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task is None:
        db.close()
        flash("Задача не найдена", "error")
        return redirect(admin_url("works"))
    if request.method == "POST":
        title = request.form["title"].strip()
        statement = request.form["statement"].strip()
        input_format = request.form["input_format"].strip()
        output_format = request.form["output_format"].strip()
        if not title:
            flash("Укажите название задачи")
        else:
            db.execute(
                "UPDATE tasks SET title = ?, statement = ?, input_format = ?, output_format = ? WHERE id = ?",
                (title, statement, input_format, output_format, task_id),
            )
            db.commit()
    db.close()
    return redirect(admin_url(f"work-{task['work_id']}task-{task_id}"))


@app.route("/admin/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def admin_task_delete(task_id):
    db = get_db()
    task = db.execute("SELECT id, work_id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task:
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()
    db.close()
    flash("Задача удалена", "success")
    return redirect(admin_url(f"work-{task['work_id']}"))


# --- тесты

def task_work_id(db, task_id):
    row = db.execute("SELECT work_id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return row["work_id"] if row else None


@app.route("/admin/tasks/<int:task_id>/tests/new", methods=["POST"])
@login_required
@role_required("admin")
def admin_test_new(task_id):
    input_data = request.form["input_data"]
    output_data = request.form["output_data"]
    db = get_db()
    work_id = task_work_id(db, task_id)
    if output_data.strip() == "":
        flash("Тест должен содержать ожидаемый вывод", "error")
    else:
        db.execute(
            "INSERT INTO tests (task_id, input_data, output_data) VALUES (?, ?, ?)",
            (task_id, input_data, output_data),
        )
        db.commit()
    db.close()
    return redirect(admin_url(f"work-{work_id}task-{task_id}"))


@app.route("/admin/tasks/<int:task_id>/tests/bulk", methods=["POST"])
@login_required
@role_required("admin")
def admin_test_bulk(task_id):
    db = get_db()
    work_id = task_work_id(db, task_id)
    raw = request.form.get("bulk_data", "")
    try:
        tests = parse_bulk_tests(raw)
    except ValueError as e:
        flash(str(e))
        db.close()
        return redirect(admin_url(f"work-{work_id}task-{task_id}"))
    if not tests:
        flash("Не найдено ни одного теста")
    else:
        db.executemany(
            "INSERT INTO tests (task_id, input_data, output_data) VALUES (?, ?, ?)",
            [(task_id, inp, out) for inp, out in tests],
        )
        db.commit()
    db.close()
    return redirect(admin_url(f"work-{work_id}task-{task_id}"))


@app.route("/admin/tests/<int:test_id>/edit", methods=["POST"])
@login_required
@role_required("admin")
def admin_test_edit(test_id):
    db = get_db()
    test = db.execute("SELECT * FROM tests WHERE id = ?", (test_id,)).fetchone()
    if test is None:
        db.close()
        flash("Тест не найден", "error")
        return redirect(admin_url("works"))
    task = db.execute("SELECT work_id FROM tasks WHERE id = ?", (test["task_id"],)).fetchone()
    work_id = task["work_id"] if task else None
    input_data = request.form["input_data"]
    output_data = request.form["output_data"].strip()
    if not output_data:
        flash("Тест должен содержать ожидаемый вывод", "error")
    else:
        db.execute(
            "UPDATE tests SET input_data = ?, output_data = ? WHERE id = ?",
            (input_data, output_data, test_id),
        )
        db.commit()
    db.close()
    return redirect(admin_url(f"work-{work_id}task-{test['task_id']}"))


@app.route("/admin/tests/<int:test_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def admin_test_delete(test_id):
    db = get_db()
    test = db.execute("SELECT id, task_id FROM tests WHERE id = ?", (test_id,)).fetchone()
    if test:
        work_id = db.execute("SELECT work_id FROM tasks WHERE id = ?", (test["task_id"],)).fetchone()["work_id"]
        db.execute("DELETE FROM tests WHERE id = ?", (test_id,))
        db.commit()
        flash("Тест удалён", "success")
    else:
        work_id = None
    db.close()
    return redirect(admin_url(f"work-{work_id}task-{test['task_id']}"))


# --- студенты

@app.route("/admin/students")
@login_required
@role_required("admin")
def admin_students():
    return redirect(admin_url("students"))


@app.route("/admin/students/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_student_new():
    if request.method == "POST":
        login_val = request.form["login"].strip()
        full_name = request.form["full_name"].strip()
        if not login_val:
            flash("Укажите логин студента")
        else:
            db = get_db()
            exists = db.execute("SELECT id FROM users WHERE login = ?", (login_val,)).fetchone()
            if exists:
                flash("Студент с таким логином уже существует", "error")
            else:
                password = generate_password()
                db.execute(
                    "INSERT INTO users (login, password_hash, role, full_name, password_show) VALUES (?, ?, 'student', ?, ?)",
                    (login_val, generate_password_hash(password), full_name, password),
                )
                db.commit()
                flash(f"Студент «{login_val}» создан. Пароль: {password}", "success")
            db.close()
        return redirect(admin_url("students"))
    return redirect(admin_url("students"))


@app.route("/admin/students/<int:user_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_student_edit(user_id):
    if request.method == "GET":
        return redirect(admin_url("students"))
    db = get_db()
    student = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if student is None or student["role"] != "student":
        db.close()
        flash("Студент не найден", "error")
        return redirect(admin_url("students"))
    login_val = request.form["login"].strip()
    full_name = request.form["full_name"].strip()
    if not login_val:
        flash("Укажите логин")
    else:
        dup = db.execute("SELECT id FROM users WHERE login = ? AND id != ?", (login_val, user_id)).fetchone()
        if dup:
            flash("Студент с таким логином уже существует", "error")
        else:
            db.execute("UPDATE users SET login = ?, full_name = ? WHERE id = ?", (login_val, full_name, user_id))
            db.commit()
    db.close()
    return redirect(admin_url("students"))


@app.route("/admin/students/<int:user_id>/reset", methods=["POST"])
@login_required
@role_required("admin")
def admin_student_reset(user_id):
    db = get_db()
    student = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if student is None or student["role"] != "student":
        db.close()
        flash("Студент не найден", "error")
    else:
        password = generate_password()
        db.execute(
            "UPDATE users SET password_hash = ?, password_show = ? WHERE id = ?",
            (generate_password_hash(password), password, user_id),
        )
        db.commit()
        flash(f"Новый пароль студента «{student['login']}»: {password}", "success")
    db.close()
    return redirect(admin_url("students"))


@app.route("/admin/students/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def admin_student_delete(user_id):
    db = get_db()
    student = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if student:
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
        flash("Студент удалён", "success")
    db.close()
    return redirect(admin_url("students"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)