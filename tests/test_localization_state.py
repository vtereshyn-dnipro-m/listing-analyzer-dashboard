# -*- coding: utf-8 -*-
"""
tests/test_localization_state.py — «только английский» означает, что
переводов НЕТ, а не «не доделан ни один язык».

25.09, после первого чтения Figma с модулями A+, три воздуходувки
в списке стали «Только англ.» — при 97 переведённых строках из 107
на ES и IT. Ничего не потерялось и всё сошлось по слотам (проверено
запросом: `Main Images` 30 из 30, дыры только в новых модулях A+);
неверным был ЯРЛЫК. Язык считался готовым лишь при нуле пробелов,
а состояний было три — все / частично / только англ., — и товар,
у которого ни один язык не доделан, попадал в «только англ.» вместе
с товаром, где не начинали. Экран называл английскими карточки,
переведённые на девять десятых.

Цифры в наборе — живые, из базы 25.09 (`figma_layers`):

    B0GTW2CTWZ  ES: карточка 30/30, A+ 67/77   IT: 30/30, 67/77
    B0H26QX9DJ  ES: карточка 51/51, A+ 42/52   IT: 51/51, 38/52
    B0DG2Y9MSS  ES: карточка 39/39, A+ 32/44   IT: 39/39, 34/44
    B0G4S9SJ3M  DE: карточка 33/33, A+ 54/54   ES: 33/33, A+ 0/54

Стаплер здесь — контрольный: у него DE доделан целиком, и он обязан
остаться «частично», как было. Проверяется не расцветка чипа,
а СОСТОЯНИЕ и то, что покрытие названо числом.

Запуск (pytest не нужен):  python tests/test_localization_state.py
"""
from __future__ import annotations

import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import services.db                                       # noqa: E402
services.db.get_conn = lambda: type("C", (), {"close": lambda self: None})()

import services.localization as loc                      # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def cov(main: tuple, aplus: tuple) -> dict:
    return {"done": main[0] + aplus[0], "total": main[1] + aplus[1],
            "main": list(main), "aplus": list(aplus)}


def product(langs: dict) -> dict:
    """langs: {язык: ((карточка переведено, всего), (A+ переведено, всего))}"""
    c = {lg: cov(*v) for lg, v in langs.items()}
    for lg in loc.TARGET_LANGS:
        c.setdefault(lg, cov((0, 33), (0, 54)))
    done = {lg for lg, v in c.items() if v["done"] >= v["total"]}
    return {"lang_cov": c, "langs_done": done}


# --- 1. живые случаи: 97 из 107 — это «частично», а не «английский»
BLOWERS = {
    "B0GTW2CTWZ": {"es": ((30, 30), (67, 77)), "it": ((30, 30), (67, 77))},
    "B0H26QX9DJ": {"es": ((51, 51), (42, 52)), "it": ((51, 51), (38, 52))},
    "B0DG2Y9MSS": {"es": ((39, 39), (32, 44)), "it": ((39, 39), (34, 44))},
}
for asin, langs in BLOWERS.items():
    r = product(langs)
    es = r["lang_cov"]["es"]
    check(f"{asin}: ES {es['done']}/{es['total']} — «частично», не «только англ.»",
          loc.row_state(r) == "partial")

# --- 2. стаплер: DE доделан целиком — состояние прежнее
_stapler = product({"de": ((33, 33), (54, 54)), "es": ((33, 33), (0, 54))})
check("стаплер с готовым DE остаётся «частично»",
      loc.row_state(_stapler) == "partial" and "de" in _stapler["langs_done"])

# --- 3. границы: пусто и всё
_empty = product({})
check("ни одной переведённой строки — «только англ.»",
      loc.row_state(_empty) == "none")
_full = product({lg: ((33, 33), (54, 54)) for lg in loc.TARGET_LANGS})
check("все языки без пробелов — «все языки»", loc.row_state(_full) == "all")
_one_line = product({"es": ((1, 33), (0, 54))})
check("одна переведённая строка — уже не «английский», но и не «готов»",
      loc.row_state(_one_line) == "partial")
# без покрытия (демо-набор, старые данные) поведение прежнее
check("без покрытия судим по готовым языкам, как раньше",
      loc.product_state({"de"}) == "partial" and loc.product_state(set()) == "none")

# --- 4. шапка считает те же состояния
_sum = loc.summarize(pd.DataFrame([product(l) for l in BLOWERS.values()]
                                  + [_full, _empty]))
check(f"в шапке три частичных, один готов, один английский ({_sum})",
      _sum == {"total": 5, "all": 1, "partial": 3, "none": 1})

# --- 5. покрытие считается из слоёв, и A+ отделён от карточки
COV_ROWS = pd.DataFrame([
    # слайд карточки: переведён на ES и IT
    {"product_id": 7, "slot": "B0GTW2CTWZ.PT01#0", "source_text": "Blower",
     "char_limit": 20, "have": {"es", "it"}},
    # модуль A+: переведён только на ES
    {"product_id": 7, "slot": "B0GTW2CTWZ.A+d01#0", "source_text": "Warranty",
     "char_limit": 20, "have": {"es"}},
    # мобильный модуль: не переведён нигде
    {"product_id": 7, "slot": "B0GTW2CTWZ.A+m01#0", "source_text": "Two years",
     "char_limit": 20, "have": set()},
])
loc._coverage = lambda product_id=None: COV_ROWS
loc.lang_coverage.clear()
_c = loc.lang_coverage()[7]
check(f"ES: карточка 1/1, A+ 1/2 ({_c['es']})",
      _c["es"]["main"] == [1, 1] and _c["es"]["aplus"] == [1, 2]
      and _c["es"]["done"] == 2 and _c["es"]["total"] == 3)
check("IT: карточка переведена, модули нет",
      _c["it"]["main"] == [1, 1] and _c["it"]["aplus"] == [0, 2])
check("DE: не начинали", _c["de"]["done"] == 0 and _c["de"]["total"] == 3)
check("пробелы считаются от того же покрытия",
      loc.lang_gaps()[7] == {"de": 3, "es": 1, "it": 2, "fr": 3})

# --- 6. чип называет покрытие числом, а подсказка разносит по местам
# Страницу целиком исполнять нельзя — нужен рантайм Streamlit; берём
# из исходника ровно функции чипа. Так проверка не зависит от того,
# что ещё рисует страница, но смотрит на настоящий код, а не на копию.
_src = (ROOT / "pages/content.py").read_text(encoding="utf-8")
_ns: dict = {"t": lambda k, **kw: {"loc.cov_main": "Карточка",
                                   "loc.cov_aplus": "A+",
                                   "loc.cov_source": "Язык-источник",
                                   "loc.cov_none": "Строк пока нет"}.get(k, k),
             "ALL_LANGS": loc.ALL_LANGS, "OK_GREEN": "#2F6B3A", "MUTED": "#57534A"}
_start = _src.index("def cov_hint(")
_end = _src.index("def product_row_html(")
exec(compile(_src[_start:_end], "chips", "exec"), _ns)
chips = _ns["lang_chips"]

_html = chips({"de"}, _c)
check("чип показывает покрытие числом: «ES 2/3»", "ES 2/3" in _html)
check("готовый язык — без числа, как раньше",
      ">EN<" in _html and "EN " not in _html.replace("&nbsp;", " ").split("<span")[1])
check("подсказка разносит карточку и A+",
      'title="ES: Карточка 1/1 · A+ 1/2"' in _html)
check("язык без единой строки перевода — серый чип без числа",
      'title="FR: Карточка 0/1 · A+ 0/2"' in _html and "FR 0/" not in _html)
check("одной строкой, без переносов (правило 1)", "\n" not in _html)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
