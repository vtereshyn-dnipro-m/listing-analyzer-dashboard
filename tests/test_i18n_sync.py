# -*- coding: utf-8 -*-
"""
tests/test_i18n_sync.py — словарь и его рассинхрон с кодом.

Два разных отказа, и оба выглядят как «перевод пропал».

ПЕРВЫЙ — грязь в самом словаре. Паритет по МНОЖЕСТВУ ключей её не
видит: один и тот же ключ, объявленный в языке дважды, оставляет
в словаре последнее значение, а множества всё равно совпадают. Так
в английский блок однажды попали украинский и русский тексты того же
ключа — на экране повезло, победил английский. Проверка идёт по СТРОКАМ
файла, а не по разобранному словарю: иначе она слепа ровно к этому.

ВТОРОЙ — рассинхрон с кодом. Streamlit Cloud подтягивает свежие файлы,
но процесс живёт дальше и держит импортированные модули: страница
получает новый код, а `i18n` остаётся старым. Новый код зовёт ключи,
которых старый словарь не знает, и на экране появляются сырые
`synth.cov_no_sqp`. Это не регрессия перевода, а незавершённый деплой —
и приложение обязано так и сказать, а не молчать. Симптом ищется
часами, лечится ребутом за полминуты.

Судить об этом можно ТОЛЬКО по сравнению файла с модулем в памяти.
Первая версия проверки считала промахи `t()` — и объявила ребут на
ровном месте: в приложении есть места, где отсутствие перевода
штатно (подписи болей по `rule_id`, коды проблем Amazon приходят
сотнями). Такие места спрашивают словарь через `tr_opt`, и здесь
проверяется, что от их вопросов баннер молчит: ложная тревога дороже
молчания, после неё настоящую уже не воспримут всерьёз.

Запуск (pytest не нужен):  python tests/test_i18n_sync.py
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
pd.read_sql = lambda *a, **k: pd.DataFrame()

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


import i18n                                            # noqa: E402
from streamlit.testing.v1 import AppTest                # noqa: E402

SRC = (ROOT / "i18n.py").read_text(encoding="utf-8")
BLOCKS = re.split(r'(?=^    "(?:en|ru|uk)": \{)', SRC, flags=re.M)[1:]
check("в файле три языковых блока", len(BLOCKS) == 3)

LINES: dict[str, list[str]] = {}
for _b in BLOCKS:
    _lang = re.match(r'    "(\w+)"', _b).group(1)
    LINES[_lang] = re.findall(r'^        "([\w.]+)":', _b, re.M)

for _lang, _keys in LINES.items():
    _dup = sorted({k for k in _keys if _keys.count(k) > 1})
    check(f"в {_lang} нет дублей ключей ({_dup or '—'})", not _dup)

check("наборы ключей совпадают во всех трёх языках",
      set(LINES["ru"]) == set(LINES["uk"]) == set(LINES["en"]))

# плейсхолдеры: {n} в одном языке и {count} в другом — это падение
# на подстановке, а не косметика
_ph = {k: {lg: set(re.findall(r"\{(\w+)\}", i18n.LANGS[lg].get(k, "")))
           for lg in ("ru", "uk", "en")} for k in i18n.LANGS["ru"]}
_bad_ph = [k for k, v in _ph.items() if len({frozenset(s) for s in v.values()}) > 1]
check(f"плейсхолдеры совпадают ({_bad_ph or '—'})", not _bad_ph)

# --- штатный промах не поднимает тревогу
import streamlit as st                                  # noqa: E402
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
check("на живом словаре предупреждения нет", not at.sidebar.warning)

check("tr_opt возвращает None вместо ключа",
      i18n.tr_opt("issue.code.100232") is None
      and i18n.tr_opt("nav.synthesis") is not None)
_ = [i18n.t("cause.amazon_blocked"), i18n.t("action.lost_amazon_choice"),
     i18n.t("issue.code.100232")]
at1 = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
check("промахи по несуществующим ключам тревогу НЕ поднимают",
      not at1.sidebar.warning)

# --- модуль отстал от файла: вот это и есть рассинхрон
_saved = {lg: {k: i18n.LANGS[lg][k] for k in ("synth.cov_no_sqp",
                                              "export.state_here")}
          for lg in i18n.LANGS}
for _lg in i18n.LANGS:
    for _k in ("synth.cov_no_sqp", "export.state_here"):
        i18n.LANGS[_lg].pop(_k, None)
st.cache_data.clear()
at2 = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
_w = " ".join(str(w.value) for w in at2.sidebar.warning)
for _lg, _kv in _saved.items():
    i18n.LANGS[_lg].update(_kv)
st.cache_data.clear()
check("ключи в файле, которых нет в модуле, поднимают тревогу", bool(_w))
check("предупреждение называет ключи и говорит про ребут",
      "synth.cov_no_sqp" in _w and "ребут" in _w.lower())

# --- модуль старее самой проверки: тоже рассинхрон.
# Подсовываем КОПИЮ модуля без tr_opt, а не удаляем имя в оригинале:
# t() зовёт tr_opt по глобалям своего модуля и просто упал бы —
# проверялось бы падение, а не детектор. Функции копии ходят
# в оригинальные глобали и работают.
import types                                            # noqa: E402
_fake = types.ModuleType("i18n")
_fake.__dict__.update(i18n.__dict__)
del _fake.tr_opt
sys.modules["i18n"] = _fake
at3 = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
_w3 = " ".join(str(w.value) for w in at3.sidebar.warning)
sys.modules["i18n"] = i18n
check("старый i18n без tr_opt тоже виден", "i18n" in _w3)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
