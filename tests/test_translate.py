# -*- coding: utf-8 -*-
"""
tests/test_translate.py — промпт перевода и разбор ответа модели.

Промпт здесь не деталь реализации, а рабочий инструмент дизайнера:
он виден на экране целиком и правится руками. Поэтому проверяется
не «есть ли строка в тексте», а три свойства, без которых перевод
не годится.

ПРЕДЕЛ. У каждой строки своя ширина слоя, немецкий длиннее
английского примерно на пятую часть. Предел обязан доехать до модели
ПОСТРОЧНО: один общий лимит на карточку означал бы, что половина
строк не влезет, и узнаем мы об этом при экспорте.

СЛОВАРЬ. Готовые переводы дизайнера идут образцом. Их не надо
заводить руками: строка, которая есть и на UK/US, и на DE, — уже
пара. Пары, совпадающие с исходником (коды моделей, «1,500 mAh»),
остаются намеренно: модель должна видеть, что их не трогают.

ОТВЕТ. Модель отвечает JSON'ом, и мусор в нём не должен молча
превращаться в перевод: строка без текста или без места — это
пропуск, а не пустой перевод поверх работы человека.

Запуск (pytest не нужен):  python tests/test_translate.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


import services.translate as tr                           # noqa: E402

ROWS = [
    {"slot": "B0G.PT05#1", "source_text": "Cordless Freedom", "char_limit": 28},
    {"slot": "B0G.PT05#3", "source_text": "Built-in 3.6 V battery",
     "char_limit": None},
]
PAIRS = [{"en": "Fabric fastening", "tr": "Stoffbefestigung"},
         {"en": "1,500 mAh", "tr": "1,500 mAh"}]

TEXT = tr.build_prompt(tr.DEFAULT_PROMPT, "de", ROWS, PAIRS)

# --- предел доезжает до модели по КАЖДОЙ строке
check("предел строки назван числом", "не больше 28 знаков" in TEXT)
check("неизвестный предел назван неизвестным, а не нулём",
      "предел неизвестен" in TEXT and "не больше 0" not in TEXT)
check("каждая строка идёт со своим местом",
      TEXT.count("slot=") == len(ROWS))

# --- словарь дизайнера
check("готовая пара попала в промпт образцом",
      "Fabric fastening" in TEXT and "Stoffbefestigung" in TEXT)
check("пара, совпадающая с исходником, не выброшена",
      TEXT.count("1,500 mAh") >= 2)
check("язык назван человеческим словом", "немецкий" in TEXT)

# --- правила по умолчанию видны и осмысленны
check("правило про модели есть в тексте по умолчанию",
      "CC-36" in tr.DEFAULT_PROMPT)
check("правило про предел есть в тексте по умолчанию",
      "сокращай формулировку" in tr.DEFAULT_PROMPT)
# промпт целиком складывается из того, что человек видит
check("правки человека доезжают до модели",
      "НЕ ПЕРЕВОДИТЬ СЛОВО ЛАЗЕР" in
      tr.build_prompt(tr.DEFAULT_PROMPT + "\n7. НЕ ПЕРЕВОДИТЬ СЛОВО ЛАЗЕР",
                      "de", ROWS, PAIRS))

# --- ответ модели
check("нормальный ответ разбирается",
      tr.parse_reply('[{"slot":"a","text":"Akku"}]') == {"a": "Akku"})
check("объект с массивом внутри тоже разбирается",
      tr.parse_reply({"translations": [{"slot": "a", "text": "Akku"}]})
      == {"a": "Akku"})
check("строка без текста не становится пустым переводом",
      tr.parse_reply('[{"slot":"a"},{"slot":"b","text":"  "}]') == {})
check("строка без места отбрасывается",
      tr.parse_reply('[{"text":"Akku"}]') == {})
check("неразобранный ответ — пусто, а не исключение",
      tr.parse_reply("не json") == {} and tr.parse_reply(None) == {})

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
