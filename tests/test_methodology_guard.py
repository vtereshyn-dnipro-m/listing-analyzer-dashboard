# -*- coding: utf-8 -*-
"""
tests/test_methodology_guard.py — генерация без методологии не запускается.

Инцидент 29.08: в тайтлы вернулся бренд Dnipro-M, хотя активная v8 его
запрещает. Кэш промпта был ни при чём — в `load_skill()` жила ЗАПАСНАЯ
методология с зашитым текстом «Бренд Dnipro-M первым», то есть правилом,
прямо противоположным действующему. Она включалась молча при любом сбое
чтения и при отсутствии активной строки `title_split`, уходила в промпт
с версией 0, и всё выглядело нормально: генерация шла, проверки
проходили, а правила были чужие.

Отсюда проверки:

  · запасного текста в коде нет вовсе — не «нейтральный по умолчанию»,
    а никакого. Молчаливая подмена правил хуже отказа;
  · версия 0 означает «методологии нет» и останавливает генерацию;
  · причина сбоя доходит до экрана, а не подменяется правилами.

Запуск (pytest не нужен):  python tests/test_methodology_guard.py
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

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


SRC = (ROOT / "pages/synthesis.py").read_text(encoding="utf-8")


def page(sql):
    """Модуль страницы со своим ответом БД.

    st.cache_data кэширует по коду функции, а не по модулю: без clear()
    второй сценарий получил бы ответ первого.
    """
    pd.read_sql = sql
    mod = types.ModuleType("syn")
    mod.__dict__["__name__"] = "syn"
    exec(compile(SRC[:SRC.index("with feed:")], "syn", "exec"),
         mod.__dict__)
    mod.load_skill.clear()
    return mod


SKILL = pd.DataFrame([
    dict(scope="common", skill_text="Общая часть.", version=3),
    dict(scope="title_split", skill_text="Brand name is NOT included.",
         version=8),
])


def sql_ok(*a, **k):
    return SKILL.copy()


def sql_boom(*a, **k):
    raise RuntimeError("connection refused")


def sql_empty(*a, **k):
    return pd.DataFrame(columns=["scope", "skill_text", "version"])


# --- запасного текста нет в исходнике
# фраза осталась в комментарии — там она объясняет, ЧТО убрали.
# Важно, чтобы её не было в исполняемом коде
_code_lines = [ln for ln in SRC.splitlines()
               if "Бренд Dnipro-M первым" in ln
               and not ln.lstrip().startswith("#")
               and "return" in ln]
check("зашитой методологии нет в исполняемом коде", not _code_lines)
check("и вообще нет возврата текста при сбое чтения методологии",
      'return ("Бренд' not in SRC)

# --- сбой чтения
syn = page(sql_boom)
txt, ver = syn.load_skill()
check("при сбое текст пуст", txt == "")
check("при сбое версия 0", ver == 0)
check("причина сохранена", "connection refused" in (syn.skill_error() or ""))

# --- активной строки title_split нет
syn2 = page(sql_empty)
txt2, ver2 = syn2.load_skill()
check("без активной методологии текст пуст и версия 0",
      txt2 == "" and ver2 == 0)
check("и причина названа", bool(syn2.skill_error()))

# --- нормальный случай
syn3 = page(sql_ok)
txt3, ver3 = syn3.load_skill()
check("активная методология читается", "Brand name is NOT" in txt3)
check("версия та, что у title_split", ver3 == 8)
check("общая часть приклеена", "Общая часть" in txt3)
check("после успеха ошибка сброшена", syn3.skill_error() is None)

# --- генерация: версия 0 = отказ
CALLS: list = []
syn3.generate_json = lambda *a, **k: (
    CALLS.append(k.get("system", "")) or {"title": "T", "highlights": "H",
                                          "dropped": []})

res_ok = syn3.generate_split("Título", "es", txt3, [], [], kw_df=None,
                             skill_ver=8)
check("с версией 8 генерация идёт", res_ok is not None and len(CALLS) == 1)
check("методология попала в system", "Brand name is NOT" in CALLS[0])
check("версия видна в system", "версия 8" in CALLS[0])

CALLS.clear()
res_zero = syn3.generate_split("Título", "es", txt3, [], [], kw_df=None,
                               skill_ver=0)
check("версия 0 — генерация НЕ запускается",
      res_zero is None and not CALLS)

res_empty = syn3.generate_split("Título", "es", "", [], [], kw_df=None,
                                skill_ver=8)
check("пустая методология — генерация НЕ запускается",
      res_empty is None and not CALLS)

# --- «Перегенерировать» просит генерацию, а не прячет результат
check("кнопка ставит флаг перегенерации",
      'st.session_state[f"regen-{asin}-{mp}"] = True' in SRC)
check("флаг читается там же, где кнопка «Сгенерировать»",
      'st.session_state.pop(f"regen-{asin}-{mp}", False)' in SRC)
check("и запускает ТОТ ЖЕ блок генерации, а не копию",
      SRC.count("res, _st = generate_guarded(") == 1)

# --- кнопки генерации выключены без методологии
check("кнопка в очереди выключается без версии",
      "disabled=not skill_version" in SRC)
check("партия тоже", "disabled=not _top or not skill_version" in SRC)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
