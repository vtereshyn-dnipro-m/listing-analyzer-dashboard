# -*- coding: utf-8 -*-
"""
tests/test_localization.py — контроль длины перевода и честность демо.

Ради колонки длины эта страница и делается. Испанский и немецкий длиннее
английского примерно на пятую часть, слой в макете фиксированной ширины,
и текст, который в него не влез, обнаруживается при ЭКСПОРТЕ — когда
работа уже сделана и переделывать её дорого. Поэтому длина считается
до вставки, и проверяется здесь не наличие колонки, а её ответы:
влезает, впритык, не влезает, предел неизвестен.

Отдельно заперта честность демонстрационных данных. Пока Figma не
прочитана, экран показывает выдуманный набор — иначе по пустой странице
не понять, как устроена работа. Демо, неотличимое от настоящих данных,
хуже пустого экрана: по нему начнут считать объём работы. Поэтому оно
обязано объявляться плашкой, а сбой чтения — оставаться сбоем, а не
превращаться в «данных нет».

Запуск (pytest не нужен):  python tests/test_localization.py
"""
from __future__ import annotations

import pathlib
import re
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


MODE = {"fail": False}


def fake_sql(sql, con=None, **kw):
    if MODE["fail"]:
        raise RuntimeError("relation figma_products does not exist")
    return pd.DataFrame()


pd.read_sql = fake_sql

import services.localization as loc                     # noqa: E402
from streamlit.testing.v1 import AppTest                # noqa: E402
import streamlit as st                                  # noqa: E402


# --- 1. сам расчёт длины
check("влезает с запасом", loc.fits("Carga USB-C", 18)[2] == "ok")
check("не влезает — over",
      loc.fits("Se carga desde power banks y adaptadores", 34)[2] == "over")
check("впритык — отдельное состояние, а не «влезает»",
      loc.fits("x" * 19, 20)[2] == "tight")
check("длина и предел возвращаются числами",
      loc.fits("abc", 10)[:2] == (3, 10))

# Предел приходит из макета и может отсутствовать. «Не знаем предел»
# и «предел нулевой» — разные вещи, и вторая не должна выглядеть первой:
# ноль в Python ложный, и проверка через истинность их бы склеила.
check("предел неизвестен — так и сказано", loc.fits("abc", None)[2] == "unknown")
check("нулевой предел — это не «неизвестно»", loc.fits("abc", 0)[2] == "over")
check("пустой перевод при известном пределе влезает",
      loc.fits("", 10)[2] == "ok")
check("NaN вместо предела не роняет расчёт",
      loc.fits("abc", float("nan"))[2] == "unknown")

_df = pd.DataFrame([
    {"translated_text": "коротко", "char_limit": 20},
    {"translated_text": "x" * 40, "char_limit": 34},
    {"translated_text": "y" * 50, "char_limit": 34},
])
check("считаются именно непомещающиеся строки", loc.over_rows(_df) == 2)

# --- 2. сводка по товарам
_p = pd.DataFrame([
    {"langs_done": {"de", "es", "it", "fr"}},
    {"langs_done": {"es"}},
    {"langs_done": set()},
])
_s = loc.summarize(_p)
check(f"сводка считает три состояния ({_s})",
      _s == {"total": 3, "all": 1, "partial": 1, "none": 1})
check("английский не делает товар переведённым",
      loc.product_state({"en"}) == "none")

# --- 3. экран: демо объявлено, сбой назван сбоем
def page():
    st.cache_data.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    at.switch_page("pages/content.py").run()
    return at


MODE["fail"] = True
at = page()
check("страница открывается при недоступных таблицах", not at.exception)
check("сбой чтения назван сбоем",
      any("не удалось прочитать" in str(e.value).lower() for e in at.error))
check("демо объявлено плашкой",
      any("емонстрационные данные" in str(i.value) for i in at.info))
check("плашка предупреждает, что числа выдуманы",
      any("выдуман" in str(i.value) for i in at.info))

MODE["fail"] = False
at = page()
check("на пустых таблицах тоже показывается демо, а не пустой экран",
      any("емонстрационные данные" in str(i.value) for i in at.info))

# --- 4. список: очередь работы сверху
_labels = [str(b.label) for b in at.button if str(b.key or "").startswith("loc-open-")]
check(f"кнопка ведёт на непереведённый язык ({_labels[:1]})",
      bool(_labels) and _labels[0].endswith("DE"))

# --- 5. экран перевода: счётчик, подсветка, предупреждение
at.session_state["loc-product"] = -1
at.session_state["loc-lang"] = "es"
at.run()
_md = " ".join(str(m.value) for m in at.markdown)
_counters = re.findall(r">(\d+ / (?:\d+|—)(?: ⚠)?)<", _md)
check(f"у каждой строки счётчик «длина / предел» ({len(_counters)})",
      len(_counters) == len(at.text_input) and len(_counters) > 0)
check("непомещающийся перевод помечен", any("⚠" in c for c in _counters))
check("строка с превышением подсвечена целиком",
      _md.count("background:#FDF3D8") == 1)
check("под таблицей сказано, сколько строк править",
      any("Длиннее макета строк: 1" in str(w.value) for w in at.warning))
check("экспорт остаётся в Figma — это сказано на экране",
      any("Экспорт PNG" in str(c.value) for c in at.caption))

# кнопки, которых ещё нет за спиной, не должны выглядеть работающими
_apply = next((b for b in at.button if b.key == "loc-apply"), None)
_retry = next((b for b in at.button if b.key == "loc-retry"), None)
check("«Применить в Figma» заблокирована и объясняет почему",
      _apply is not None and _apply.disabled and "REST" in str(_apply.help))
check("«Перевести заново» заблокирована до подключения модели",
      _retry is not None and _retry.disabled)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
