# -*- coding: utf-8 -*-
"""
tests/test_synthesis_breakdown.py — разрез по рынкам и происхождение черновика.

Таблица по странам нужна не для красоты: строки обязаны складываться в итог.
Пока итог был единственным числом, неверный разрез выглядел бы нормально —
поэтому первая и главная проверка здесь именно про сходимость сумм.

Остальное стережёт честность подписей:

  · «Прочие» перечисляют коды свёрнутых стран, иначе строка беспамятна;
  · выбранная фильтром страна не сворачивается в «Прочие» — иначе
    подсвечивать нечего и разрез не проверить;
  · плашка модели не выдумывает вендора для незнакомого имени;
  · история не пишет «отклонено»: отказ нигде не сохраняется, и черновик,
    который просто перегенерировали, отклонённым не был.

Запуск (pytest не нужен):  python tests/test_synthesis_breakdown.py
"""
from __future__ import annotations

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
pd.read_sql = lambda *a, **k: pd.DataFrame()

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def load_page():
    """Функции страницы без вкладок — как в test_batch_counts_saves."""
    src = open(ROOT / "pages/synthesis.py", encoding="utf-8").read()
    mod = types.ModuleType("syn")
    mod.__dict__["__name__"] = "syn"
    exec(compile(src[:src.index("with tab_queue:")], "syn", "exec"),
         mod.__dict__)
    return mod


syn = load_page()

# es: 20 товаров, 7 сверх лимита; de: 6 и 3; nl: 1 и 1; se: 1 и 0
QUEUE = ([{"r": {"marketplace": "es"}, "risk": 150.0} for _ in range(7)]
         + [{"r": {"marketplace": "de"}, "risk": 25.0} for _ in range(3)]
         + [{"r": {"marketplace": "nl"}, "risk": 0.0}])
ALL = pd.DataFrame([{"marketplace": "es"}] * 20 + [{"marketplace": "de"}] * 6
                   + [{"marketplace": "nl"}, {"marketplace": "se"}])


def cells(html: str) -> list[list[str]]:
    """Строки таблицы как списки текстов ячеек."""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if tds:
            out.append([re.sub(r"\s+", " ",
                               re.sub(r"<[^>]+>", "", c)).strip() for c in tds])
    return out


def num(s: str) -> float:
    digits = re.sub(r"[^\d,.-]", "", s).replace(",", "").replace(" ", "")
    return float(digits) if digits not in ("", "-", ".") else 0.0


# --- без фильтра: суммы обязаны сойтись
html = syn.market_breakdown(QUEUE, ALL, [])
table = cells(html)
check("таблица построена", len(table) >= 3)
total = next((r for r in table if r[0].startswith("Итого")), None)
body = [r for r in table if not r[0].startswith("Итого")]
check("есть строка итога", total is not None)
if total and body:
    check("товары строк складываются в итог",
          sum(num(r[1]) for r in body) == num(total[1]) == 28)
    check("«сверх лимита» складывается в итог",
          sum(num(r[2]) for r in body) == num(total[2]) == 11)
    check("деньги складываются в итог",
          abs(sum(num(r[4]) for r in body) - num(total[4])) < 1
          and abs(num(total[4]) - 1125) < 1)

check("страны названы по-человечески",
      "Испания" in html and "Германия" in html)
check("мелкие страны свёрнуты в «Прочие»", "Прочие" in html)
check("«Прочие» перечисляют коды свёрнутых стран",
      re.search(r"Прочие[^|]*?nl, se", re.sub(r"<[^>]+>", "", html)) is not None)
check("свёрнутые страны не показаны отдельными строками",
      not any(r[0].startswith("Нидерланды") for r in table))

# --- фильтр: подсветка и защита от сворачивания
sel_es = syn.market_breakdown(QUEUE, ALL, ["es"])
rows_es = re.findall(r'<tr style="([^"]*)"[^>]*>(.*?)</tr>', sel_es, re.S)
hi = [r for r in rows_es if "FBF3EC" in r[0]]
check("выбранный рынок подсвечен ровно один", len(hi) == 1)
check("подсвечен именно он", "Испания" in hi[0][1] if hi else False)

sel_nl = syn.market_breakdown(QUEUE, ALL, ["nl"])
check("выбранная мелкая страна не уехала в «Прочие»",
      "Нидерланды" in sel_nl)
check("одиночную мелочь не сворачиваем в «Прочие» из одной строки",
      "Прочие" not in sel_nl)
check("итог не поехал от фильтра",
      num(next(r for r in cells(sel_nl) if r[0].startswith("Итого"))[1]) == 28)

# --- плашка модели
check("вендор выведен из имени модели",
      "Anthropic" in syn.model_badge("claude-sonnet-5")
      and "claude-sonnet-5" in syn.model_badge("claude-sonnet-5"))
check("gemini опознан", "Google Gemini" in syn.model_badge("gemini-3.5-flash"))
check("незнакомая модель не получает выдуманного вендора",
      syn.model_badge("mystery-7b").count("·") == 0
      and "mystery-7b" in syn.model_badge("mystery-7b"))
check("пустая модель не рисует плашку",
      syn.model_badge(None) == "" and syn.model_badge(float("nan")) == "")

# --- история черновиков
acc = {"accepted_at": pd.Timestamp("2026-08-28 10:00")}
check("принято: дата и число заходов до него",
      syn.history_line({"drafts": 7, "before_accept": 6, "after_accept": 0}, acc)
      == "принят 28.08 · до этого черновиков: 6")
check("принято с первого раза — без лишнего хвоста",
      syn.history_line({"drafts": 1, "before_accept": 0, "after_accept": 0}, acc)
      == "принят 28.08")
check("черновики после принятия названы отдельно",
      "после принятия черновиков: 2" in syn.history_line(
          {"drafts": 9, "before_accept": 6, "after_accept": 2}, acc))
check("не принято — сказано прямо",
      syn.history_line({"drafts": 7}, None)
      == "черновиков: 7 · ни один не принят")
check("слова «отклонено» нет ни в одном варианте",
      all("отклон" not in syn.history_line(d, a) for d, a in (
          ({"drafts": 7, "before_accept": 6, "after_accept": 0}, acc),
          ({"drafts": 7}, None))))
check("пусто, когда работы не было", syn.history_line({}, None) == "")

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
