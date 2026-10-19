# -*- coding: utf-8 -*-
"""
tests/run_all.py — весь набор `tests/test_*.py` одной командой; его зовёт CI.

Тесты — скрипты, а не pytest (AGENTS.md, «Тесты»): каждый исполняется в
своём процессе, код возврата — итог. Сюда же входят проверки синтаксиса,
импорта и переводов. Базы и секретов не нужно: всё, что ходит наружу,
подменено в самих тестах. Если тест падает только без секретов — это поломка
теста, а не окружения: в CI секретов нет и не будет.

Запуск:  python tests/run_all.py            — все
         python tests/run_all.py i18n bsr   — только с этими словами в имени
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
TIMEOUT_S = 900

only = sys.argv[1:]
tests = [p for p in sorted((ROOT / "tests").glob("test_*.py"))
         if not only or any(w in p.name for w in only)]
failed = []
t0 = time.time()
for p in tests:
    s = time.time()
    try:
        r = subprocess.run([sys.executable, str(p)], cwd=ROOT, capture_output=True, text=True, timeout=TIMEOUT_S)
        rc, out = r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        rc, out = -1, f"не уложился в {TIMEOUT_S} с"
    mark = "OK  " if rc == 0 else "FAIL"
    print(f"{mark} {time.time() - s:6.1f}s  {p.name}", flush=True)
    if rc != 0:
        failed.append(p.name)
        lines = [l for l in out.splitlines() if "FAIL" in l or "Error" in l or "ИТОГ" in l][-15:]
        for l in lines or out.splitlines()[-15:]:
            print("        " + l)
print()
print(f"ИТОГ: {len(tests) - len(failed)} из {len(tests)} прошли за {time.time() - t0:.0f} с"
      + (f"; упали: {', '.join(failed)}" if failed else ""))
sys.exit(1 if failed or not tests else 0)
