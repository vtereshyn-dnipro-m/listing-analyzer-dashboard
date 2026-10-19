# -*- coding: utf-8 -*-
"""
tests/test_imports.py — каждый модуль приложения импортируется без базы и
секретов.

Ловит то, чего компиляция не видит: имя, которого нет в соседнем модуле
(`ImportError: cannot import name 'last_call_error'` — так уже было), модуль,
который при импорте ходит в базу или читает секрет. Страницы (`app.py`,
`pages/`) — скрипты Streamlit: при импорте они рисуют экран, их покрывают
компиляция и AppTest в остальных тестах.

Каждый модуль импортируется в ОТДЕЛЬНОМ процессе с пустым окружением: иначе
модуль, импортированный раньше, прятал бы недостающий импорт следующего.

Запуск (pytest не нужен):  python tests/test_imports.py
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

MODULES = (["i18n", "config", "auth", "access_screen"]
           + [f"services.{p.stem}" for p in sorted((ROOT / "services").glob("*.py")) if p.stem != "__init__"]
           + [f"components.{p.stem}" for p in sorted((ROOT / "components").glob("*.py")) if p.stem != "__init__"])

# Пустое окружение: ни DATABASE_URL, ни ключей. Нужны только путь и язык.
ENV = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "LANG", "TMPDIR", "TEMP", "TMP") if k in os.environ}
ENV["HOME"] = ENV.get("TMPDIR") or ENV.get("TEMP") or "/tmp"
ENV["PYTHONPATH"] = str(ROOT)

bad = []
for m in MODULES:
    r = subprocess.run([sys.executable, "-c", f"import {m}"], cwd=ROOT, env=ENV,
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        tail = (r.stderr.strip().splitlines() or ["?"])[-1]
        bad.append(f"{m}: {tail[:200]}")
print(f"  {'OK  ' if not bad else 'FAIL'} импортируется {len(MODULES) - len(bad)} из {len(MODULES)} модулей")
for b in bad:
    print("       " + b)
print()
print("ИТОГ:", "все проверки прошли" if not bad else f"{len(bad)} провалов")
sys.exit(1 if bad else 0)
