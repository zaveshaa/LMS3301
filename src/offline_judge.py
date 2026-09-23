import os
import resource
import subprocess
import tempfile
import time


class JudgeUnavailable(Exception):
    pass


class OfflineUnavailable(JudgeUnavailable):
    pass


TIMEOUT_SECONDS = 5
MAX_OUTPUT_CHARS = 10000


def _normalize(text):
    if text is None:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip(" \t\n")


def _limit_memory():
    try:
        resource.setrlimit(
            resource.RLIMIT_AS,
            (256 * 1024 * 1024, 256 * 1024 * 1024),
        )
    except (ValueError, resource.error):
        pass


def _run(code, stdin):
    with tempfile.TemporaryDirectory(prefix="lms-judge-") as td:
        script = os.path.join(td, "main.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write(code)
        started = time.monotonic()
        try:
            proc = subprocess.run(
                ["/usr/bin/python3", script],
                input=stdin or "",
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                cwd=td,
                preexec_fn=_limit_memory,
            )
        except FileNotFoundError:
            raise OfflineUnavailable("Интерпретатор python3 не найден")
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
