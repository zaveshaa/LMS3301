# LMS3301

A small LMS for an introductory programming course. Students get lectures and practical assignments, submit solutions, and the system runs them against tests and reports per-test results. The teacher manages works, tasks, tests, and students.

Stack: Python 3, Flask, SQLite. Frontend is server-rendered Jinja2 templates, no build step and no external dependencies.

## Features

Student:

- list of visible works (visibility limited by group);
- lectures and practical assignments;
- in-browser code editing, draft persisted in localStorage;
- submission — automatic test run, per-test verdict (OK/WA/TLE/RE);
- local run of the solution on custom input without submitting.

Teacher (admin):

- works, tasks, tests — add, edit, bulk test import;
- students by group, account creation and password reset (password shown once);
- grading, manual review, re-running automatic checks;
- overview of all submissions with status filter and search.

## Verdicts

Student code runs in an isolated process:

- macOS: launched via `sandbox-exec` with a profile that denies network, reading user files, and spawning processes; writes are allowed only into the judge's temp directory;
- resource limits: 256 MB memory, 5 s time, max 8 processes, 64 open file descriptors, 1 MB output file;
- interpreter runs with `-I -B` flags (isolated mode, no `.pyc`).

If `sandbox-exec` is unavailable on the platform, the judge runs without a sandbox and solutions go to manual review — automatic checking on such systems is not guaranteed. Expected output is compared to actual after normalizing line endings and trailing whitespace.

## Run

```bash
pip install flask
python3 src/app.py
```

On first start, `src/lms.db` is created with demo works and tests. The server listens on `http://localhost:5000` (debug mode is enabled).

Demo logins:

- teacher: `admin` / `admin`
- student: `5952_1` / `5952_1`

Student login format is `group_number`, e.g. `101_5` — the group is derived from the prefix before the first underscore.

## Layout

```
src/
  app.py              routes, access control, submission handling
  db.py               schema, migrations, demo data
  offline_judge.py    code execution, sandbox, verdicts
  sys_console.py      system console (processes, load)
  templates/          Jinja2 templates
```

## Database

SQLite, file `src/lms.db` (gitignored). The schema is created and migrated on startup (`init_db`). Main tables: `users`, `works`, `tasks`, `tests`, `submissions`, `submission_tests`, `work_groups`.

Passwords are stored only as hashes (werkzeug `generate_password_hash`). The plaintext password is shown once at account creation or reset and is not stored.

## License

MIT, see `LICENSE`.