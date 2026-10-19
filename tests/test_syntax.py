# -*- coding: utf-8 -*-
"""
tests/test_syntax.py — каждый .py репозитория компилируется.

Проверка — `compile`, а не `ast.parse`: `return` на верхнем уровне страницы
`ast.parse` пропускает, а `compile` нет (AGENTS.md, «Вход через Google и
роли»). На Streamlit Cloud такая страница выглядела бы мёртвой. Файлы берутся
из git: всё, что уедет на Cloud, и ничего из локальных `_probe_*`.

Запуск (pytest не нужен):  python tests/test_syntax.py
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def tracked_py() -> list[pathlib.Path]:
    try:
        out = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.split()
        return [ROOT / p for p in out]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in ROOT.rglob("*.py") if ".venv" not in p.parts and "venv" not in p.parts]


files = tracked_py()
bad = []
for p in files:
    try:
        compile(p.read_bytes(), str(p), "exec")
    except SyntaxError as e:
        bad.append(f"{p.relative_to(ROOT)}:{e.lineno}: {e.msg}")
print(f"  {'OK  ' if not bad else 'FAIL'} компилируется {len(files) - len(bad)} из {len(files)} файлов")
for b in bad:
    print("       " + b)
check_count = len(files) > 50
print(f"  {'OK  ' if check_count else 'FAIL'} файлы найдены ({len(files)}), а не пустой список")
print()
ok = not bad and check_count
print("ИТОГ:", "все проверки прошли" if ok else f"провалов: {len(bad) + (not check_count)}")
sys.exit(0 if ok else 1)
