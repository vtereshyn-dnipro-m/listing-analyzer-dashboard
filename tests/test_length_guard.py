# -*- coding: utf-8 -*-
"""
tests/test_length_guard.py — гарантия лимита длины.

Модель промахивается по длине (77 при лимите 75), и раньше человек жал
«Перегенерировать» руками. Здесь проверяется весь механизм: запас
в промпте, автоповтор с точным указанием, обрезка по границе слова
и отказ резать, если теряется must_keep-фраза.

Запуск (pytest не нужен):  python tests/test_length_guard.py
"""
import sys, pathlib, types
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import services.db
services.db.get_conn = lambda: type("C", (), {"close": lambda self: None})()
pd.read_sql = lambda *a, **k: pd.DataFrame()

src = open(ROOT / "pages/synthesis.py", encoding="utf-8").read()
head = src[:src.index("def save_draft")]
mod = types.ModuleType("syn"); mod.__dict__["__name__"] = "syn"
exec(compile(head, "syn", "exec"), mod.__dict__)

fails = []
def check(n, c):
    print(("  OK   " if c else "  FAIL ") + n)
    if not c: fails.append(n)

L = mod.TITLE_LIMIT
check(f"лимит title = {L}", L == 75)

# --- промпт: запас и самопроверка
PROMPTS = []
mod.generate_json = lambda task, prompt, **kw: (PROMPTS.append(prompt), RESP.pop(0))[1]
RESP = [{"title": "x" * 40, "highlights": "y" * 40, "dropped": []}]
mod.generate_split("исходный тайтл", "es", "методика", [], [])
p0 = PROMPTS[0]
check("в промпте цель = лимит минус запас", f"целься в {L - 2} символов" in p0)
check("в промпте правило самопроверки длины", "посчитай длину" in p0)

# --- автоповтор: два промаха, потом попадание
PROMPTS.clear()
RESP[:] = [{"title": "z" * 80, "highlights": "h", "dropped": []},
           {"title": "z" * 77, "highlights": "h", "dropped": []},
           {"title": "z" * 70, "highlights": "h", "dropped": []}]
res, stats = mod.generate_guarded("t", "es", "s", [], [], None, [])
check("уложились с третьей попытки", len(res["title"]) == 70)
check("попыток 3, автоповторов 2",
      stats["attempts"] == 3 and stats["retried"] == 2)
check("резать не пришлось", stats["trimmed"] == 0 and stats["over"] == 0)
check("в повторе названа фактическая длина и лимит",
      "был 80 символов при лимите 75" in PROMPTS[1])
check("в повторе сказано на сколько сократить",
      "сократи РОВНО на 7 символов" in PROMPTS[1])
check("в повторе запрет добавлять слова", "Не добавляй новых слов" in PROMPTS[1])

# --- три промаха -> режем по границе слова
PROMPTS.clear()
LONG = "Dnipro-M Martillo Perforador SDS Plus 1650W 5,5J Taladro Percutor Profesional Maletin"
RESP[:] = [{"title": LONG, "highlights": "h", "dropped": []}] * 3
res, stats = mod.generate_guarded("t", "es", "s", [], [], None, ["Dnipro-M"])
check("после трёх неудач обрезали", stats["trimmed"] == 1)
check("уложились в лимит", len(res["title"]) <= L)
check("обрезано по границе слова, не посреди",
      LONG.startswith(res["title"]) and (len(LONG) == len(res["title"])
                                         or LONG[len(res["title"])] in " ,"))
check("хвостовая пунктуация убрана", not res["title"].endswith((" ", ",", "·")))
check("поле помечено как обрезанное", res.get("trimmed_fields") == ["title"])
check("must_keep на месте", "Dnipro-M" in res["title"])

# --- обрезка убила бы must_keep -> не режем
PROMPTS.clear()
RESP[:] = [{"title": LONG, "highlights": "h", "dropped": []}] * 3
res, stats = mod.generate_guarded("t", "es", "s", [], [], None, ["Maletin"])
check("не режем, если теряется must_keep",
      stats["trimmed"] == 0 and stats["over"] == 1)
check("длина осталась превышенной — честнее, чем потерять фразу",
      len(res["title"]) > L)
check("поле помечено как не уложившееся", res.get("over_fields") == ["title"])

# --- обрезка никогда не делит слово
for lim in range(20, 60, 7):
    cut = mod.trim_to_word(LONG, lim)
    ok = len(cut) <= lim and (LONG[len(cut)] in " ," if len(cut) < len(LONG) else True)
    if not ok:
        check(f"граница слова при лимите {lim}", False); break
else:
    check("обрезка не делит слово ни на одном лимите", True)

# --- highlights тоже под гарантией
PROMPTS.clear()
HL = "y" * 200
RESP[:] = [{"title": "ok", "highlights": HL, "dropped": []}] * 3
res, stats = mod.generate_guarded("t", "es", "s", [], [], None, [])
check("highlights обрезаны до 125", len(res["highlights"]) <= 125)

print()
print("ИТОГ:", "все проверки прошли" if not fails else f"{len(fails)} провалов: {fails}")
sys.exit(1 if fails else 0)
