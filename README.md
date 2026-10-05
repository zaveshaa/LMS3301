# LMS3301

A small LMS for an introductory programming course. Students read lectures and
practical assignments, submit solutions, and the system runs them against tests
and reports per-test verdicts. The teacher manages works, tasks, tests, students
and grades.

Stack: Python 3, Flask, SQLite. Server-rendered Jinja2 templates, no build step.

## Install and run

```bash
git clone <repo-url>
cd LMS3301
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app src/app.py run
```

Open http://127.0.0.1:5000.

If `python3` is a conda or Anaconda install, `venv` can fail on `ensurepip`.
Create the environment with a plain interpreter instead:

```bash
/usr/bin/python3 -m venv .venv
```

On the first start `src/lms.db` is created and one teacher account is made. Its
password is printed to the terminal once and stored only as a hash.

To set the password yourself:

```bash
LMS_ADMIN_PASSWORD=yourpassword flask --app src/app.py run
```

Demo content (sample works, lectures, tasks, a demo student) is opt-in:

```bash
LMS_DEMO=1 flask --app src/app.py run
```

Demo logins are `admin` / `admin` and `5952_1` / `5952_1`.

To start from an empty database, delete `src/lms.db` and run again.

## Configuration

All variables are optional.

| Variable | Default | Meaning |
| --- | --- | --- |
| `LMS_SECRET_KEY` | generated into `src/.secret_key` | Session signing key |
| `LMS_ADMIN_LOGIN` | `admin` | Teacher login created on first start |
| `LMS_ADMIN_PASSWORD` | random, printed once | Teacher password on first start |
| `LMS_DEMO` | off | `1` seeds demo content |
| `LMS_HOST` | `127.0.0.1` | Bind address |
| `LMS_PORT` | `5000` | Bind port |
| `LMS_JUDGE_PYTHON` | `/usr/bin/python3` | Interpreter used to run student code |
| `LMS_JUDGE_TIMEOUT` | `5` | Seconds per test |
| `LMS_JUDGE_MEMORY_MB` | `256` | Memory limit per run |

Set `LMS_HOST=0.0.0.0` to serve a class over the network. Put the app behind a
real WSGI server and HTTPS before doing that.

## Running it as a server

Single machine, macOS, in a classroom:

```bash
export LMS_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export LMS_ADMIN_PASSWORD=...
export LMS_HOST=0.0.0.0
flask --app src/app.py run
```

`flask run` is the development server. For anything longer than a demo put it
behind a real WSGI server:

```bash
pip install gunicorn
gunicorn --chdir src --bind 0.0.0.0:8000 app:app
```

Use systemd or launchd to keep it running. Back up `src/lms.db`; it holds
everything. SQLite is fine for one classroom.

### The judge is macOS only

Student code runs under `sandbox-exec`, which exists only on macOS.

On Linux the judge finds no sandbox, refuses to execute anything, and every
submission is marked as waiting for manual review. Nothing runs unisolated,
but there is no automatic checking either.

To get automatic checking on a Linux server, the judge has to run each solution
in a throwaway container with no network, a memory cap and a process cap. That
runner is not implemented. Until it is, use a macOS machine for the judge.

## Layout

```
src/
  app.py              routes, access control, submissions
  db.py               schema, migrations, demo data
  offline_judge.py    code execution, sandbox, verdicts
  templates/          Jinja2 templates
```

## Using it

Student: works visible to their group, in-browser editor with a localStorage
draft, submission with per-test verdicts, and a local run on custom input
without submitting.

Teacher: works, tasks and tests (add, edit, bulk import), students by group,
account creation and password reset, grading, manual review, re-running checks,
and an overview of all submissions with filtering and search.

Student login format is `group_number`, for example `101_5`. The group is the
prefix before the first underscore and controls which works are visible.

The first two tests of a task are the public examples shown to students. The
rest stay hidden.

## Verdicts

OK, WA, TLE, MLE, RE. Output is compared after normalizing line endings and
trailing whitespace.

Student code runs in a separate process group under `sandbox-exec` with network,
writes and reading of `/Users`, `/etc` and the private user directories denied.
The run is killed when it exceeds the time limit, the memory limit, or the
output file limit, and the whole group is killed with it.

The sandbox is macOS only. If `sandbox-exec` is missing the judge refuses to
execute anything and submissions go to manual review, so no code runs
unisolated. The current judge state is shown in the teacher panel.

## Database

SQLite, file `src/lms.db`, gitignored. The schema is created on startup. Main
tables: `users`, `works`, `tasks`, `tests`, `submissions`, `submission_tests`,
`work_groups`.

Passwords are stored only as hashes. The plaintext password is shown once at
account creation or reset and is not stored.

Timestamps are ISO 8601 in UTC.

## Security notes

- Session keys are never committed; set `LMS_SECRET_KEY` in production.
- All state-changing routes require a CSRF token, logout included.
- Login attempts, local runs and submissions are rate limited.
- Passwords are hashed with werkzeug.
- SQL is parameterized throughout.

## Not implemented yet

Export of submissions to Google Sheets or CSV, grading points, an audit log of
grade changes, and a background queue for judging.

## License

MIT, see `LICENSE`.