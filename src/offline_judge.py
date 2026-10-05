import os
import resource
import signal
import subprocess
import sys
import tempfile
import time

SANDBOX_EXEC = "/usr/bin/sandbox-exec" if os.path.exists("/usr/bin/sandbox-exec") else None

def _pick_python():
    override = os.environ.get("LMS_JUDGE_PYTHON")
    if override:
        return override
    for candidate in ("/usr/bin/python3", "/usr/local/bin/python3", "/usr/bin/python"):
        if os.path.exists(candidate):
            return candidate
    return sys.executable or "python3"


PYTHON = _pick_python()

TIMEOUT_SECONDS = int(os.environ.get("LMS_JUDGE_TIMEOUT", "5"))
MEMORY_LIMIT_MB = int(os.environ.get("LMS_JUDGE_MEMORY_MB", "256"))
OUTPUT_FILE_LIMIT = 1024 * 1024
MAX_OUTPUT_CHARS = 10000
POLL_INTERVAL = 0.02

MAX_PROCESSES = 8
MAX_OPEN_FILES = 64

OK = 3
TLE = 5
MLE = 6
RE = 12

SANDBOX_TEMPLATE = """
(version 1)
(allow default)
(deny network*)
(deny file-write*)
(allow file-write* (literal "/dev/null"))
(allow file-write* (subpath "%(tmp)s"))
(deny file-read-data (subpath "/Users"))
(deny file-read-data (subpath "/private/etc"))
(deny file-read-data (subpath "/Library/Preferences"))
(deny file-read-data (subpath "/Library/Application Support"))
(deny file-read-data (subpath "/Library/Logs"))
(deny file-read-data (subpath "/Library/Keychains"))
(deny file-read-data (subpath "/Library/Mobile Documents"))
(deny file-read-data (subpath "/Library/CloudStorage"))
(deny file-read-data (subpath "/Library/Containers"))
(deny file-read-data (subpath "/usr/local"))
(deny file-read-data (subpath "/opt"))
(deny file-read-data (subpath "/Volumes"))
(deny file-read-data (subpath "/private/var/db"))
(deny file-read-data (subpath "/private/var/log"))
(deny process-fork)
"""


class JudgeUnavailable(Exception):
    pass


class OfflineUnavailable(JudgeUnavailable):
    pass


def _normalize(text):
    if text is None:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip(" \t\n")


def _secure_rlimits():
    limits = [
        (resource.RLIMIT_CPU, (TIMEOUT_SECONDS + 1, TIMEOUT_SECONDS + 1)),
        (resource.RLIMIT_NPROC, (MAX_PROCESSES, MAX_PROCESSES)),
        (resource.RLIMIT_NOFILE, (MAX_OPEN_FILES, MAX_OPEN_FILES)),
        (resource.RLIMIT_FSIZE, (OUTPUT_FILE_LIMIT, OUTPUT_FILE_LIMIT)),
    ]
    for what, value in limits:
        try:
            resource.setrlimit(what, value)
        except (ValueError, OSError, resource.error) as exc:
            print("judge: cannot set %s: %s" % (what, exc), file=sys.stderr)


def _rss_kb(pid):
    try:
        out = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return int(out) if out else 0
    except (ValueError, OSError, subprocess.SubprocessError):
        return 0


def _kill_group(proc):
    for sig in (signal.SIGKILL, signal.SIGTERM):
        try:
            os.killpg(os.getpgid(proc.pid), sig)
        except (OSError, ProcessLookupError):
            return
        try:
            proc.wait(timeout=1)
            return
        except subprocess.TimeoutExpired:
            continue


def _build_cmd(script, tmp_dir):
    if not os.path.exists(PYTHON):
        raise OfflineUnavailable("Интерпретатор не найден: %s" % PYTHON)
    cmd = [PYTHON, "-I", "-B", script]
    if not SANDBOX_EXEC:
        raise OfflineUnavailable("Песочница недоступна: нет %s" % SANDBOX_EXEC)
    profile = SANDBOX_TEMPLATE % {"tmp": tmp_dir}
    return [SANDBOX_EXEC, "-p", profile] + cmd


def _run(code, stdin):
    if not code.strip():
        raise OfflineUnavailable("Пустой код")

    with tempfile.TemporaryDirectory(prefix="lms-judge-") as td:
        script = os.path.join(td, "main.py")
        real_tmp = os.path.realpath(td)
        with open(script, "w", encoding="utf-8") as f:
            f.write(code)

        cmd = _build_cmd(script, real_tmp)

        stdin_path = os.path.join(td, "stdin")
        stdout_path = os.path.join(td, "stdout")
        stderr_path = os.path.join(td, "stderr")
        with open(stdin_path, "w", encoding="utf-8") as f:
            f.write(stdin or "")

        started = time.monotonic()
        with open(stdin_path) as fin, open(stdout_path, "w+b") as fout, open(stderr_path, "w+b") as ferr:
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=fin, stdout=fout, stderr=ferr,
                    cwd=real_tmp,
                    preexec_fn=_secure_rlimits,
                    start_new_session=True,
                )
            except (FileNotFoundError, PermissionError, OSError) as exc:
                raise OfflineUnavailable("Изоляция решения недоступна: %s" % exc)

            deadline = started + TIMEOUT_SECONDS
            limit_kb = MEMORY_LIMIT_MB * 1024
            peak_kb = 0
            verdict = None

            while proc.poll() is None:
                now = time.monotonic()
                if now > deadline:
                    verdict = TLE
                    break
                rss = _rss_kb(proc.pid)
                if rss > peak_kb:
                    peak_kb = rss
                if rss > limit_kb:
                    verdict = MLE
                    break
                time.sleep(POLL_INTERVAL)

            if verdict is not None:
                _kill_group(proc)
                return {
                    "status_id": verdict,
                    "stdout": "",
                    "stderr": "",
                    "peak_kb": peak_kb,
                    "elapsed": round(time.monotonic() - started, 3),
                }

            returncode = proc.returncode
            fout.seek(0)
            ferr.seek(0)
            out = fout.read(MAX_OUTPUT_CHARS)
            err = ferr.read(MAX_OUTPUT_CHARS)

        if returncode is not None and returncode < 0 and -returncode in (signal.SIGKILL, signal.SIGXFSZ):
            status_id = MLE if -returncode == signal.SIGKILL and peak_kb > limit_kb else RE
        else:
            status_id = OK if returncode == 0 else RE

        return {
            "status_id": status_id,
            "stdout": out.decode("utf-8", "replace"),
            "stderr": err.decode("utf-8", "replace"),
            "peak_kb": peak_kb,
            "elapsed": round(time.monotonic() - started, 3),
        }


def _verdict(status_id, test, data):
    if status_id == OK:
        actual = _normalize(data.get("stdout"))
        expected = _normalize(test["output_data"])
        return {
            "passed": actual == expected,
            "actual": actual,
            "error": "" if actual == expected else "Вывод не совпадает",
        }
    if status_id == TLE:
        return {"passed": False, "actual": "", "error": "Превышено время выполнения"}
    if status_id == MLE:
        return {
            "passed": False,
            "actual": "",
            "error": "Превышен лимит памяти (%d МБ)" % MEMORY_LIMIT_MB,
        }
    err = (data.get("stderr") or "").strip()
    return {
        "passed": False,
        "actual": "",
        "error": "Ошибка выполнения" + (": " + err[:200] if err else ""),
    }


def check_code(code, tests):
    results = []
    for t in tests:
        data = _run(code, t["input_data"])
        results.append(_verdict(data.get("status_id"), t, data))
    return True, results


def run_code(code, stdin):
    data = _run(code, stdin or "")
    return {
        "status_id": data.get("status_id"),
        "stdout": data.get("stdout", ""),
        "stderr": data.get("stderr", ""),
        "peak_kb": data.get("peak_kb", 0),
        "elapsed": data.get("elapsed", 0),
    }


def judge_status():
    return {
        "sandbox": SANDBOX_EXEC is not None,
        "python": PYTHON,
        "timeout": TIMEOUT_SECONDS,
        "memory_mb": MEMORY_LIMIT_MB,
    }