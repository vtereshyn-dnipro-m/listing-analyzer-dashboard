# -*- coding: utf-8 -*-
"""
tests/test_methodology_page.py — методология обязана доходить до экрана.

Инцидент 30.08: страница «Методологии» для ЛЮБОЙ области показывала «для
этой области методологии ещё нет», хотя в базе лежала активная v8.
Причина — `conn.close()` в загрузчике при том, что переменной `conn` там
уже не было: её убрали при переходе на SQLAlchemy-движок (PR #44), строку
закрытия оставили. `NameError` ловился общим `except Exception` и
превращался в пустую таблицу.

Дороже всего не то, что методология не видна, а то, куда страница вела
дальше: редактор пуст, версия считается нулевой, кнопка предлагает
«Сохранить как v1». Нажатие деактивировало бы действующую версию и
сделало активной новую — то есть сбой чтения молча приводил к ПОТЕРЕ
методологии, а следом и к генерации по пустым правилам.

Отсюда три проверки, и все три про одно: сбой чтения не имеет права
выглядеть как «данных нет».

Запуск (pytest не нужен):  python tests/test_methodology_page.py
"""
from __future__ import annotations

import pathlib
import sys

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


SKILL = pd.DataFrame([dict(
    id=30, version=8, marketplace="all",
    skill_text="Ключевая фраза первой, бренд в тайтл не выносить.",
    created_at=pd.Timestamp("2026-08-29 10:00"), is_active=True)])

MODE = {"fail": False}


def fake_sql(sql, conn=None, **kw):
    s = str(sql)
    if "FROM synthesis_skill" in s:
        if MODE["fail"]:
            raise RuntimeError("connection refused")
        return SKILL.copy()
    return pd.DataFrame()


pd.read_sql = fake_sql
import streamlit as st                                  # noqa: E402
from streamlit.testing.v1 import AppTest                # noqa: E402


def page():
    st.cache_data.clear()          # кэш загрузчика общий на процесс
    a = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    a.switch_page("pages/methodology.py").run()
    return a


def texts(a) -> str:
    return " ".join(
        [str(m.value) for m in a.markdown] + [str(c.value) for c in a.caption]
        + [str(i.value) for i in a.info] + [str(e.value) for e in a.error]
        + [str(w.value) for w in a.warning])


def save_button(a):
    return next((b for b in a.button
                 if "Сохранить как" in str(b.label)), None)


# --- база отвечает: методология обязана быть на экране
MODE["fail"] = False
at = page()
check("страница отрисована", not at.exception)
check("активная версия показана", "v8" in texts(at))
check("текст методологии подставлен в редактор",
      any("бренд в тайтл не выносить" in str(ta.value) for ta in at.text_area))
check("страница НЕ говорит «методологии ещё нет»",
      "методологии ещё нет" not in texts(at))
check("кнопка предлагает следующую версию, а не первую",
      (b := save_button(at)) is not None and "v9" in str(b.label))

# --- база недоступна: «сломалось» не должно выглядеть как «пусто»
MODE["fail"] = True
at = page()
check("при сбое чтения страница жива", not at.exception)
check("сбой назван сбоем, а не отсутствием данных",
      any("прочитать" in str(e.value) or "connection refused" in str(e.value)
          for e in at.error))
check("предложения создать первую версию нет",
      "методологии ещё нет" not in texts(at))
# главное: писать поверх непрочитанного нельзя — так и терялась v8
b = save_button(at)
check("сохранение заблокировано, пока методология не прочитана",
      b is None or b.disabled)
check("редактор не предлагает пустой текст под запись",
      all(ta.disabled for ta in at.text_area) or not at.text_area)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
