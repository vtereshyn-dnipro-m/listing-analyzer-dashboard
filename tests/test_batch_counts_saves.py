# -*- coding: utf-8 -*-
"""
tests/test_batch_counts_saves.py — партия считает СОХРАНЁННОЕ, не сгенерированное.

Раньше batch_generate увеличивал done сразу после генерации, а результат
save_draft игнорировал. Если вставка падала (например, колонки нет в схеме),
партия рапортовала «5 готово», вкладка разбора оставалась пустой, и человек
искал причину в генерации. Ровно тот молчаливый провал, из-за которого
началась вся история с доставкой ошибок.

Запуск (pytest не нужен):  python tests/test_batch_counts_saves.py
"""
from __future__ import annotations

import pathlib
import sys
import types

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import services.db                                     # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


class _Cur:
    """Курсор, который падает на INSERT в synthesis_drafts — как Lakebase
    при расхождении схемы («column ... does not exist»)."""

    def __init__(self, fail_on: str | None):
        self.fail_on = fail_on

    def execute(self, sql, params=None):
        if self.fail_on and self.fail_on in str(sql):
            raise Exception(
                'column "change_type" of relation "listing_changes" '
                "does not exist")

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def make_conn(fail_on: str | None):
    class _Conn:
        def cursor(self):
            return _Cur(fail_on)

        def commit(self):
            pass

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return _Conn


def load_page(fail_on: str | None):
    """Модуль страницы с подменённым подключением и генерацией."""
    services.db.get_conn = make_conn(fail_on)
    pd.read_sql = lambda *a, **k: pd.DataFrame()
    src = open(ROOT / "pages/synthesis.py", encoding="utf-8").read()
    mod = types.ModuleType("syn")
    mod.__dict__["__name__"] = "syn"
    # берём только функции страницы, до кода вкладок
    head = src[:src.index("with tab_queue:")]
    exec(compile(head, "syn", "exec"), mod.__dict__)
    mod.generate_json = lambda task, prompt, **kw: {
        "title": "Dnipro-M короткий тайтл", "highlights": "хайлайты",
        "dropped": []}
    mod.st.session_state.clear()
    return mod


ITEMS = [{"r": {"asin": f"B0S{i:03d}", "marketplace": "es",
                "title": "Длинный тайтл " * 8},
          "draft": {}, "risk": 0.0} for i in range(5)]

# --- вставка падает: сгенерировано 5, сохранено 0
mod = load_page(fail_on="INSERT INTO synthesis_drafts")
mod.build_keyword_table = lambda *a, **k: pd.DataFrame()
out = mod.batch_generate(ITEMS, "методика", 1)
check("сохранено 0, а не 5", out["done"] == 0)
check("несохранённые посчитаны отдельно", out["unsaved"] == 5)
check("это не считается ошибкой генерации", out["failed"] == 0)
check("причина каждого провала записана", len(out["errors"]) == 5)
check("в причине виден товар и текст ошибки схемы",
      "B0S000" in out["errors"][0]
      and "does not exist" in out["errors"][0])
check("названо, что именно не сохранилось",
      "черновик не сохранён" in out["errors"][0])

# --- вставка проходит: сохранено 5
mod = load_page(fail_on=None)
mod.build_keyword_table = lambda *a, **k: pd.DataFrame()
out_ok = mod.batch_generate(ITEMS, "методика", 1)
check("при рабочей вставке сохранено 5", out_ok["done"] == 5)
check("несохранённых нет", out_ok["unsaved"] == 0)
check("ошибок нет", not out_ok["errors"])

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
