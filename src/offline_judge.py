import os
import resource
import subprocess
import tempfile
import time

if os.path.exists("/usr/bin/sandbox-exec"):
    SANDBOX_EXEC = "/usr/bin/sandbox-exec"
else:
    SANDBOX_EXEC = None


class JudgeUnavailable(Exception):
    pass


class OfflineUnavailable(JudgeUnavailable):
    pass


TIMEOUT_SECONDS = 5
MAX_OUTPUT_CHARS = 10000
MEMORY_LIMIT = 256 * 1024 * 1024

SANDBOX_TEMPLATE = """
(version 1)
(allow default)
(deny network*)
(deny file-write*)
(deny file-read-data (subpath "/Users"))
(deny file-read-data (subpath "/private/etc"))
(allow file-write* (subpath "%(tmp)s"))
(deny process-fork)
"""


def _normalize(text):
    if text is None:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip(" \t\n")


def _secure_rlimits():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
        resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT_SECONDS, TIMEOUT_SECONDS))
        resource.setrlimit(resource.RLIMIT_NPROC, (8, 8))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    except (ValueError, resource.error):
        pass


def _run(code, stdin):
    with tempfile.TemporaryDirectory(prefix="lms-judge-") as td:
        script = os.path.join(td, "main.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write(code)
        cmd = ["/usr/bin/python3", "-I", "-B", script]
        if SANDBOX_EXEC:
            tmp = td.replace("/var/", "/private/var/", 1)
            cmd = [SANDBOX_EXEC, "-p", SANDBOX_TEMPLATE % {"tmp": tmp}] + cmd
        started = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                input=stdin or "",
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                cwd=td,
                preexec_fn=_secure_rlimits,
            )
        except (FileNotFoundError, PermissionError) as exc:
            raise OfflineUnavailable("Изоляция решения недоступна: %s" % exc)
        except subprocess.TimeoutExpired as exc:
            return {
                "status_id": 5,
                "stdout": (exc.stdout or "")[:MAX_OUTPUT_CHARS],
                "stderr": (exc.stderr or "")[:MAX_OUTPUT_CHARS],
                "elapsed": TIMEOUT_SECONDS,
            }
        return {
            "status_id": 3 if proc.returncode == 0 else 12,
            "stdout": (proc.stdout or "")[:MAX_OUTPUT_CHARS],
            "stderr": (proc.stderr or "")[:MAX_OUTPUT_CHARS],
            "elapsed": round(time.monotonic() - started, 3),
        }


def _verdict(status_id, test, data):
    if status_id == 3:
        actual = _normalize(data.get("stdout"))
        expected = _normalize(test["output_data"])
        return {
            "passed": actual == expected,
            "actual": actual,
            "error": "" if actual == expected else "Вывод не совпадает",
        }
    if status_id == 5:
        return {"passed": False, "actual": "", "error": "Превышено время выполнения"}
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
        "elapsed": data.get("elapsed", 0),
    }