# -*- coding: utf-8 -*-
"""
tests/test_deploy_sync.py — новый код после мержа без ребута Streamlit Cloud (deploy_sync.py).

Проверяется то, на чём механизм может тихо не сработать:
1. номер коммита читается из .git — обычная ветка, ветка только в packed-refs, отделённая голова;
2. время старта процесса разбирается из /proc/self/stat (имя процесса со скобками и пробелами) и мусор даёт None;
3. восемь сеансов, одновременно увидевших новый коммит, сбрасывают модули ОДИН раз;
4. сам исполняемый скрипт (`__main__`) и сам deploy_sync из sys.modules не выгружаются.

Запуск (pytest не нужен):  python tests/test_deploy_sync.py
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import deploy_sync as d  # noqa: E402

FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("  OK   " if ok else "  FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=cwd, check=True,
                   capture_output=True)


print("1. номер коммита из .git")
with tempfile.TemporaryDirectory() as tmp:
    _git(tmp, "init", "-q", "-b", "main")
    pathlib.Path(tmp, "a.txt").write_text("1")
    _git(tmp, "add", ".")
    _git(tmp, "commit", "-qm", "1")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp, capture_output=True, text=True).stdout.strip()
    old_root = d.ROOT
    d.ROOT = tmp
    try:
        check("обычная ветка", d.current_commit() == sha, d.current_commit() or "None")
        _git(tmp, "pack-refs", "--all")
        check("ветка только в packed-refs", d.current_commit() == sha, d.current_commit() or "None")
        _git(tmp, "checkout", "-q", "--detach")
        check("отделённая голова", d.current_commit() == sha, d.current_commit() or "None")
    finally:
        d.ROOT = old_root

print("2. время старта процесса из /proc")
stat = "4242 (my (odd) proc) S 1 4242 4242 0 -1 4194560 100 0 0 0 5 3 0 0 20 0 7 0 12345 1000 50"
got = d._parse_start(stat, "cpu 1\nbtime 1700000000\n", 100)
check("имя процесса со скобками и пробелами", got == 1700000000 + 123.45, str(got))
check("мусор даёт None", d._parse_start("ерунда", "btime 1", 100) is None)

print("3. один сброс на много сеансов")
saved = (dict(d._state), d.current_commit, d._forget_old_session_objects)
d._state["commit"] = "old"
d.current_commit = lambda: "new"
d._forget_old_session_objects = lambda now: None
resets: list[bool] = []
threads = [threading.Thread(target=lambda: resets.append(d.sync())) for _ in range(8)]
[t.start() for t in threads]
[t.join() for t in threads]
d._state.clear()
d._state.update(saved[0])
d.current_commit, d._forget_old_session_objects = saved[1], saved[2]
check("8 сеансов — 1 сброс", sum(resets) == 1, f"сбросов {sum(resets)}")

print("4. что не выгружается")
real_main = sys.modules.get("__main__")
fake_main = types.ModuleType("__main__")
fake_main.__file__ = os.path.join(d.ROOT, "app.py")
sys.modules["__main__"] = fake_main
try:
    names = {n for n, _ in d._project_modules()}
finally:
    if real_main is not None:
        sys.modules["__main__"] = real_main
check("__main__ не выгружается", "__main__" not in names)
check("сам deploy_sync не выгружается", d.__name__ not in names)

print()
if FAILS:
    print(f"ИТОГ: провалено {len(FAILS)}: {', '.join(FAILS)}")
    sys.exit(1)
print("ИТОГ: все проверки прошли")
