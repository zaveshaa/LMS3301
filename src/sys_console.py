#!/usr/bin/env python3
"""Живая консоль-панель: CPU, нагрузка, память, активность офлайн-судьи."""
import os
import shutil
import subprocess
import sys
import time


def _cmd(*args, timeout=10):
    try:
        r = subprocess.run(list(args), capture_output=True, text=True, timeout=timeout)
        return (r.returncode, r.stdout)
    except Exception:
        return (-1, "")


def top_processes(n=8):
    rc, out = _cmd("ps", "-axo", "pid,%cpu,%mem,etime,comm")
    if rc != 0:
        return []
    lines = out.splitlines()[1:]
    rows = []
    for ln in lines:
        parts = ln.split(None, 4)
        if len(parts) < 5:
            continue
        try:
            cpu = float(parts[1].rstrip("%"))
        except ValueError:
            continue
        rows.append({"pid": parts[0], "cpu": cpu, "mem": parts[2].rstrip("%"),
                     "etime": parts[3], "name": os.path.basename(parts[4])})
    rows.sort(key=lambda r: r["cpu"], reverse=True)
    return rows[:n]


def load():
    try:
        return tuple(os.getloadavg())
    except Exception:
        return (0.0, 0.0, 0.0)


def cores():
    return os.cpu_count() or 1


def judge_active():
    rc, out = _cmd("pgrep", "-fl", "offline_judge")
    procs = [ln for ln in out.splitlines() if ln and os.path.basename(ln.split()[-1] if ln.split() else "") == "main.py"] if rc == 0 else []
    return len([p for p in procs if p])


def mem_total_mb():
    rc, out = _cmd("sysctl", "-n", "hw.memsize")
    try:
        return int(out.strip()) // (1024 * 1024)
    except Exception:
        return 0


def temp_smc():
    return None


def bar(pct, width=22):
    pct = max(0.0, min(100.0, pct))
    filled = round(pct / 100 * width)
    return "#" * filled + "." * (width - filled)


def clear():
    sys.stdout.write("\x1b[2J\x1b[H")


def panel(prev_judge_runs):
    cores_n = cores()
    l1, l5, l15 = load()
    top = top_processes()
    judge_now = judge_active()
    mem_mb = mem_total_mb()
    clock = time.strftime("%H:%M:%S")

    lines = []
    lines.append("=" * 58)
    lines.append("  LMS3301 · консоль системы        %s" % clock)
    lines.append("=" * 58)
    lines.append("")
    lines.append("  Ядра: %d   Load: %.2f / %.2f / %.2f   (норма < %d)" %
                 (cores_n, l1, l5, l15, cores_n))
    lines.append("  Память: %d МБ  |  CPU bar (1м): %s %.0f%%" %
                 (mem_mb, bar(l1 / cores_n * 100), l1 / cores_n * 100))
    lines.append("")

    if judge_now:
        lines.append("  \033[1;31mОФЛАЙН-СУДЬЯ АКТИВЕН\033[0m — сейчас идёт прогон чьего-то решения (%d процесс)" % judge_now)
    else:
        lines.append("  Офлайн-судья: простаивает (решений не проверяется)")
    lines.append("")

    if temp := temp_smc():
        lines.append("  Температура: %d°C" % temp)
    else:
        lines.append("  Температура: (нужен SMC-инструмент, см. примечание)")
    lines.append("")

    lines.append("  ТОП CPU:")
    lines.append("  %-7s %6s %6s %8s  %s" % ("PID", "%CPU", "%MEM", "ВРЕМЯ", "ПРОЦЕСС"))
    for r in top:
        mark = "  \033[1m<--\033[0m" if r["name"] in ("python3", "mdworker_shared") and r["cpu"] > 30 else ""
        lines.append("  %-7s %6.1f %6.1f %8s  %s %s" %
                     (r["pid"], r["cpu"], float(r["mem"]) if _f(r["mem"]) else 0, r["etime"],
                      r["name"][:34], mark))
    lines.append("")

    if prev_judge_runs:
        lines.append("  Судья: %d прогонов за последние 20 c (пиковые, короткие)" % prev_judge_runs)
    lines.append("=" * 58)
    return "\n".join(lines)


def _f(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def main():
    prev_runs = 0
    window = []
    try:
        while True:
            clear()
            print(panel(prev_runs))
            try:
                time.sleep(2)
            except KeyboardInterrupt:
                break
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
