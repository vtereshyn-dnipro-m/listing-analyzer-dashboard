# -*- coding: utf-8 -*-
"""
tests/test_prompt_cache.py — кэш промпта живёт на совпадении байтов.

Кэш Anthropic — это совпадение ПРЕФИКСА (порядок tools → system → messages).
Отсюда всё остальное: постоянная часть обязана быть побайтово одинаковой
от товара к товару, а всё меняющееся обязано лежать после неё. Метка
cache_control сама по себе не гарантирует ничего — при «уехавшем» префиксе
она только оплачивает запись, которую никто не прочитает.

Проверки делятся на две половины, и обе нужны:

  · кэш РАБОТАЕТ — system одинаков для разных товаров, а тайтл, маркетплейс,
    фразы и подсказка автоповтора в него не попадают;
  · кэш ИНВАЛИДИРУЕТСЯ — смена текста методологии или её версии меняет
    байты system. Без этого генерации молча пошли бы по старой методологии,
    и заметить это было бы нечем.

Запуск (pytest не нужен):  python tests/test_prompt_cache.py
"""
from __future__ import annotations

import pathlib
import sys
import types

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import services.db                                     # noqa: E402
services.db.get_conn = lambda: type(
    "C", (), {"close": lambda self: None})()
pd.read_sql = lambda *a, **k: pd.DataFrame()

import services.ai as ai                               # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def load_page():
    src = open(ROOT / "pages/synthesis.py", encoding="utf-8").read()
    mod = types.ModuleType("syn")
    mod.__dict__["__name__"] = "syn"
    exec(compile(src[:src.index("with tab_queue:")], "syn", "exec"),
         mod.__dict__)
    return mod


syn = load_page()

SKILL = "Дели тайтл на title и highlights. " * 40
CALLS: list[dict] = []


def fake_generate(task, prompt, images=None, timeout=240, system=None):
    CALLS.append({"task": task, "prompt": prompt, "system": system})
    return {"title": "T", "highlights": "H", "dropped": []}


syn.generate_json = fake_generate


def gen(title, mp="es", keep=(), retry_note="", skill=SKILL, ver=7):
    return syn.generate_split(title, mp, skill, list(keep), [],
                              kw_df=None, retry_note=retry_note, skill_ver=ver)


# --- разделение: что где лежит
gen("Taladro Dnipro-M 20V muy largo", keep=["taladro dnipro"])
call = CALLS[-1]
check("system передан отдельно", bool(call["system"]))
check("методология ушла в system", "Дели тайтл" in call["system"])
check("методологии нет в user-части", "Дели тайтл" not in call["prompt"])
check("тайтл ушёл в user", "Taladro Dnipro-M 20V" in call["prompt"])
check("тайтла нет в system", "Taladro" not in call["system"])
check("маркетплейс в user, не в system",
      "es" in call["prompt"] and "маркетплейс" not in call["system"])
check("фразы в user, не в system",
      "taladro dnipro" in call["prompt"]
      and "taladro dnipro" not in call["system"])
check("правила и формат ответа остались в system",
      "MUST KEEP" in call["system"] and '"dropped"' in call["system"])

# --- главное: system одинаков для разных товаров
CALLS.clear()
for i in range(3):
    gen(f"Título del producto número {i}", mp=("es", "de", "it")[i],
        keep=[f"фраза {i}"])
systems = {c["system"] for c in CALLS}
prompts = {c["prompt"] for c in CALLS}
check("постоянная часть побайтово одна на все товары", len(systems) == 1)
check("переменная часть у каждого своя", len(prompts) == 3)

# --- автоповтор не должен ломать кэш партии
CALLS.clear()
gen("Título largo", retry_note="Сократи title на 4 символа.")
gen("Título largo")
check("подсказка автоповтора ушла в user",
      "Сократи title" in CALLS[0]["prompt"])
check("автоповтор не тронул system",
      CALLS[0]["system"] == CALLS[1]["system"])

# --- инвалидация: смена методологии обязана менять байты
base = CALLS[-1]["system"]
CALLS.clear()
gen("Título largo", skill=SKILL + " Новое правило.")
check("правка текста методологии меняет постоянную часть",
      CALLS[-1]["system"] != base)
CALLS.clear()
gen("Título largo", ver=8)
check("смена ВЕРСИИ методологии меняет постоянную часть",
      CALLS[-1]["system"] != base)
check("версия видна в тексте", "версия 8" in CALLS[-1]["system"])
CALLS.clear()
gen("Título largo")
check("без изменений постоянная часть возвращается прежней",
      CALLS[-1]["system"] == base)

# --- тело запроса к Anthropic
body = ai._anthropic_body("claude-sonnet-5", [{"type": "text", "text": "u"}],
                          8000, "disabled", "СИСТЕМА")
check("system в теле — список блоков", isinstance(body.get("system"), list))
check("на блоке стоит cache_control ephemeral",
      body["system"][0].get("cache_control") == {"type": "ephemeral"})
check("текст system дошёл", body["system"][0]["text"] == "СИСТЕМА")
check("данные товара остались в messages",
      body["messages"][0]["content"][0]["text"] == "u")
check("без system ключа в теле нет",
      "system" not in ai._anthropic_body(
          "claude-sonnet-5", [{"type": "text", "text": "u"}], 8000, "adaptive"))

# --- учёт токенов
ai.st = type("S", (), {"session_state": {}})()
ai.reset_usage()
ai._record_usage({"input_tokens": 300, "output_tokens": 200,
                  "cache_creation_input_tokens": 1500,
                  "cache_read_input_tokens": 0})
ai._record_usage({"input_tokens": 300, "output_tokens": 200,
                  "cache_creation_input_tokens": 0,
                  "cache_read_input_tokens": 1500})
tot = ai.usage_totals()
check("вызовы посчитаны", tot["calls"] == 2)
check("запись в кэш посчитана", tot["cache_creation_input_tokens"] == 1500)
check("чтение из кэша посчитано", tot["cache_read_input_tokens"] == 1500)
check("полная цена посчитана отдельно", tot["input_tokens"] == 600)
ai.reset_usage()
check("сброс обнуляет счётчик", not ai.usage_totals())

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
