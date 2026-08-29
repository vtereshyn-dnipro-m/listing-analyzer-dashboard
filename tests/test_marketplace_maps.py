# -*- coding: utf-8 -*-
"""
tests/test_marketplace_maps.py — карты маркетплейсов не должны расходиться.

Маркетплейс упоминается в четырёх независимых картах, и каждая молчит
по-своему, когда страны в ней нет:

  · `mp.<код>` в i18n — в таблицах вместо названия появляется код («IE»
    рядом с «Испания»). Заметно глазу, но безобидно;
  · `MP_COUNTRY` в matrix_setup — фолбэк «us», и ScrapingDog идёт
    на amazon.com. Снапшот приезжает от ЧУЖОГО листинга: тайтл, цена
    и отзывы чужие, а выглядит как обычные данные. Самое дорогое молчание
    из четырёх;
  · `MP_LANGUAGE` — фолбэк «en», и длина тайтла считается по чужому языку
    (та же причина, по которой параметр вообще появился);
  · `MARKETPLACE_REGION` в spapi — отправка отказывает «неизвестный
    регион». Отказ громкий, но найдётся только в момент отправки.

Косметический симптом («IE вместо Ирландии») и порча данных здесь — одна
и та же дыра. Поэтому проверяем не подписи, а СОГЛАСОВАННОСТЬ карт.

Запуск (pytest не нужен):  python tests/test_marketplace_maps.py
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def literal_map(path: str, name: str) -> dict:
    """Карта читается из ИСХОДНИКА, а не импортом: matrix_setup.py при
    импорте поднимает всю страницу Streamlit."""
    src = (ROOT / path).read_text(encoding="utf-8")
    m = re.search(name + r"\s*=\s*(\{.*?\n\})", src, re.S)
    assert m, f"{name} не найдена в {path}"
    return ast.literal_eval(m.group(1))


COUNTRY = literal_map("pages/matrix_setup.py", "MP_COUNTRY")
LANGUAGE = literal_map("pages/matrix_setup.py", "MP_LANGUAGE")
REGION = literal_map("services/spapi.py", "MARKETPLACE_REGION")

import i18n                                            # noqa: E402
LABELS = {k[3:] for k in i18n.LANGS["ru"] if k.startswith("mp.")}

# --- то, ради чего задача и пришла
for code, human in (("ie", "Ирландия"), ("be", "Бельгия")):
    check(f"{code}: есть человеческое название",
          code in LABELS and i18n.LANGS["ru"][f"mp.{code}"] == human)
    check(f"{code}: страна сбора не уедет в фолбэк «us»",
          COUNTRY.get(code) not in (None, "us"))
    check(f"{code}: язык страницы задан", bool(LANGUAGE.get(code)))
    check(f"{code}: регион SP-API известен", REGION.get(code) == "eu")

# --- главное: карты согласованы между собой
no_label = sorted((set(COUNTRY) | set(REGION)) - LABELS)
check(f"у каждого рынка есть подпись (без неё: {no_label or '—'})",
      not no_label)

no_country = sorted(set(LANGUAGE) - set(COUNTRY))
check(f"язык задан только там, где задана страна ({no_country or '—'})",
      not no_country)

no_language = sorted(set(COUNTRY) - set(LANGUAGE))
check(f"у каждой страны сбора есть язык ({no_language or '—'})",
      not no_language)

# --- подписи одинаково полны во всех трёх языках
for lang in ("uk", "en"):
    other = {k[3:] for k in i18n.LANGS[lang] if k.startswith("mp.")}
    check(f"набор подписей в {lang} совпадает с ru", other == LABELS)

# --- незнакомый код не должен превращаться в сырой ключ
check("незнакомый код показывается заглавными, а не «mp.xx»",
      i18n.mp_label("zz") == "ZZ" and "mp." not in i18n.mp_label("zz"))
check("регистр кода не важен", i18n.mp_label("IE") == i18n.mp_label("ie"))

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
