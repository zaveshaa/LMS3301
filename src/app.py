import os
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from db import get_db, init_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = "pytestlms-dev-secret-key"

ROLE_LABELS = {"admin": "Преподаватель", "student": "Студент"}
TYPE_LABELS = {"lecture": "Лекция", "practical": "Практика"}


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
    }


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
        flash("Неверный логин или пароль")
    return render_template("login.html")


@app.route("/home")
@login_required
def home():
    user = get_user()
    if user["role"] == "student":
        return redirect(url_for("student_cabinet"))
    return render_template("home.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/student")
@login_required
@role_required("student")
def student_cabinet():
    db = get_db()
    works = db.execute("SELECT * FROM works ORDER BY type, id").fetchall()
    db.close()
    return render_template("cabinet.html", works=works)


@app.route("/student/works/<int:work_id>")
@login_required
@role_required("student")
def student_work(work_id):
    db = get_db()
    work = db.execute("SELECT * FROM works WHERE id = ?", (work_id,)).fetchone()
    if work is None:
        flash("Работа не найдена")
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
    task = db.execute("SELECT * FROM tasks WHERE id = ? AND work_id = ?", (task_id, work_id)).fetchone()
    if work is None or task is None:
        flash("Задача не найдена")
        return redirect(url_for("student_cabinet"))
    tests = db.execute("SELECT * FROM tests WHERE task_id = ?", (task_id,)).fetchall()
    db.close()
    return render_template("task_detail.html", work=work, task=task, tests=tests)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)