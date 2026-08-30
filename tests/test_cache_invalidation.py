# -*- coding: utf-8 -*-
"""
tests/test_cache_invalidation.py — сброс кэша не должен быть ковровым.

`st.cache_data.clear()` сносит ВСЕ кэши приложения, а не свой. После
приёмки одного тайтла заново читались каталог, диагнозы, экономика, SQP
и трёхмегабайтные шаблоны flat file: десять запросов там, где по делу
нужен один.

Проверяется не «есть ли кэш», а ЦЕНА действия в запросах к базе —
именно она и была проблемой. Плюс обратная сторона: перечитать нужное
всё-таки надо, иначе на экране останется старое.

Отдельно заперт вывод, который легко потерять: переключение фильтра
запросов НЕ делает. Фильтры применяются в Python поверх уже
загруженного, поэтому добавлять их в ключ кэша нельзя — каждая
комбинация стала бы отдельной записью и отдельным запросом.

Запуск (pytest не нужен):  python tests/test_cache_invalidation.py
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys
import types

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import services.db                                     # noqa: E402
services.db.get_conn = lambda: type(
    "C", (), {"close": lambda self: None})()

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


QUERIES: collections.Counter = collections.Counter()


def counting_read_sql(sql, con=None, **kw):
    m = re.search(r"FROM\s+([a-z_]+)", re.sub(r"\s+", " ", str(sql)), re.I)
    QUERIES[m.group(1) if m else "?"] += 1
    return pd.DataFrame()


pd.read_sql = counting_read_sql

import streamlit as st                                  # noqa: E402
from streamlit.testing.v1 import AppTest                # noqa: E402

PAGES = ("pages/synthesis.py", "pages/catalog.py", "pages/dashboard.py")
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
for p in PAGES:
    at.switch_page(p).run()


def cost(action) -> tuple[int, dict]:
    """Сколько запросов стоит действие: своя страница плюс возврат
    на соседние."""
    QUERIES.clear()
    action()
    at.run()
    total = sum(QUERIES.values())
    tables = dict(QUERIES)
    for p in PAGES[:2]:
        QUERIES.clear()
        at.switch_page(p).run()
        total += sum(QUERIES.values())
        tables.update(QUERIES)
    at.switch_page(PAGES[2]).run()
    return total, tables


# --- фильтр не стоит ни одного запроса
QUERIES.clear()
at.switch_page("pages/synthesis.py").run()
QUERIES.clear()
at.session_state["syn-mp"] = ["es"]
at.run()
n_filter = sum(QUERIES.values())
check(f"переключение фильтра не ходит в базу ({n_filter} запросов)",
      n_filter == 0)
QUERIES.clear()
at.session_state["syn-mp"] = ["de"]
at.run()
check("и второе переключение тоже", sum(QUERIES.values()) == 0)
at.switch_page(PAGES[2]).run()

# --- ковровый сброс: сколько стоил
global_cost, _ = cost(st.cache_data.clear)
check(f"глобальный сброс стоит дорого ({global_cost} запросов)",
      global_cost >= 8)

# --- точечная инвалидация: сколько стоит
SRC = (ROOT / "pages/synthesis.py").read_text(encoding="utf-8")
syn = types.ModuleType("syn")
syn.__dict__["__name__"] = "syn"
exec(compile(SRC[:SRC.index("with tab_queue:")], "syn", "exec"), syn.__dict__)

accept_cost, accept_tables = cost(
    lambda: syn.invalidate_change("B0AAA", "es"))
check(f"после приёмки перечитывается почти ничего ({accept_cost})",
      accept_cost <= 2)
check("и это дешевле коврового сброса в разы",
      accept_cost * 4 <= global_cost)
check("каталог, экономика и SQP после приёмки НЕ перечитываются",
      not ({"product_matrix", "asin_economics", "sqp_reports",
            "listing_attributes"} & set(accept_tables)))

import services.cache as cache                          # noqa: E402
push_cost, _ = cost(cache.after_push)
check(f"после отправки в Amazon — ноль лишних чтений ({push_cost})",
      push_cost == 0)

# --- обратная сторона: нужное всё-таки сбрасывается
seen: list = []


class _Fake:
    def __init__(self, name):
        self.name = name

    def clear(self, *a):
        seen.append((self.name, a))


syn.load_accepted = _Fake("load_accepted")
syn.load_draft_stats = _Fake("load_draft_stats")
syn.load_drafts_for_review = _Fake("load_drafts_for_review")
syn.single_plan = _Fake("single_plan")
syn.cache = types.SimpleNamespace(
    drop=cache.drop,
    after_synthesis_change=lambda *a, **k: seen.append(("services", a)))
syn.invalidate_change("B0AAA", "es")
names = [n for n, _ in seen]
check("сбрасываются очередь разбора, принятые и счётчики",
      {"load_accepted", "load_draft_stats", "load_drafts_for_review"}
      <= set(names))
check("план выгрузки сбрасывается ПО ТОВАРУ, а не целиком",
      ("single_plan", ("B0AAA", "es")) in seen)
check("группа services тоже дёргается", "services" in names)

seen.clear()
syn.invalidate_change()
check("без товара план сбрасывается целиком",
      ("single_plan", ()) in seen)

# --- сломанный сброс не роняет действие
cache.drop(None)
cache.drop(types.SimpleNamespace(clear=lambda *a: 1 / 0))
check("падение инвалидации не ломает уже записанное действие", True)

# --- ковровых сбросов в коде почти не осталось
sites = []
for p in sorted((ROOT / "pages").glob("*.py")) + \
        sorted((ROOT / "services").glob("*.py")):
    for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if re.match(r"^\s*st\.cache_data\.clear\(\)\s*$", ln):
            sites.append(f"{p.name}:{i}")
check(f"глобальный сброс остался только там, где данные общие ({sites})",
      len(sites) <= 3)
check("и каждый такой случай объяснён комментарием",
      all("ОСОЗНАННО" in (ROOT / "pages" / s.split(":")[0]).read_text(
          encoding="utf-8") or "читают ВСЕ страницы" in
          (ROOT / "pages" / s.split(":")[0]).read_text(encoding="utf-8")
          for s in sites))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
