# -*- coding: utf-8 -*-
"""
tests/test_progress.py — ход генерации виден, старый результат не мигает.

Две жалобы, обе про одно: экран не говорит, что происходит.

1. При «Сгенерировать» экран замирал. Дольше всего идут АВТОПОВТОРЫ —
   до трёх заходов, и шли они молча: человек видел зависший интерфейс
   и не знал, работа идёт или сломалось. Теперь каждый шаг уходит
   наружу через on_step, в том числе повтор с причиной.

2. При «Перегенерировать» на мгновение показывался предыдущий ПРИНЯТЫЙ
   результат — и выглядело так, будто генерация вернула старое. Причина
   в порядке отрисовки: карточка рисуется раньше блока генерации.

Проверки идут по фактическим вызовам, а не по тексту: важно не что
строки существуют, а что шаги действительно доходят и в правильном
порядке.

Запуск (pytest не нужен):  python tests/test_progress.py
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

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


SRC = (ROOT / "pages/synthesis.py").read_text(encoding="utf-8")
syn = types.ModuleType("syn")
syn.__dict__["__name__"] = "syn"
exec(compile(SRC[:SRC.index("with tab_queue:")], "syn", "exec"), syn.__dict__)

SKILL_V = 8
STEPS: list[tuple] = []


def collect(kind, **kw):
    STEPS.append((kind, kw))


# --- с первого раза: шаги идут по порядку и без лишних
RESP = [{"title": "x" * 40, "highlights": "y" * 40, "dropped": []}]
syn.generate_json = lambda *a, **k: RESP.pop(0)
STEPS.clear()
res, stats = syn.generate_guarded("t", "es", "s", [], [], None, [], SKILL_V,
                                  on_step=collect)
kinds = [k for k, _ in STEPS]
check("с первого раза: генерирую → проверяю → готово",
      kinds == ["generating", "checking", "done"])
check("повтора не было", stats["retried"] == 0)

# --- два промаха: повторы объявлены, с номером и запасом
RESP[:] = [{"title": "z" * 84, "highlights": "h", "dropped": []},
           {"title": "z" * 79, "highlights": "h", "dropped": []},
           {"title": "z" * 70, "highlights": "h", "dropped": []}]
syn.generate_json = lambda *a, **k: RESP.pop(0)
STEPS.clear()
res, stats = syn.generate_guarded("t", "es", "s", [], [], None, [], SKILL_V,
                                  on_step=collect)
kinds = [k for k, _ in STEPS]
check("три захода и два объявленных повтора",
      kinds.count("generating") == 3 and kinds.count("retry") == 2)
retries = [kw for k, kw in STEPS if k == "retry"]
check("у повтора есть номер и всего",
      retries and retries[0]["attempt"] == 2 and retries[0]["total"] == 3)
check("и сказано, на сколько был длиннее",
      retries and retries[0]["over"] == 84 - syn.TITLE_LIMIT)
check("после удачного третьего — готово", kinds[-1] == "done")

# --- три промаха: обрезка объявлена отдельно
RESP[:] = [{"title": "z" * 90, "highlights": "h", "dropped": []}] * 3
syn.generate_json = lambda *a, **k: RESP.pop(0)
STEPS.clear()
syn.generate_guarded("t", "es", "s", [], [], None, [], SKILL_V,
                     on_step=collect)
kinds = [k for k, _ in STEPS]
check("обрезка названа отдельным шагом", "trimming" in kinds)
check("и идёт после трёх генераций",
      kinds.index("trimming") > max(i for i, k in enumerate(kinds)
                                    if k == "generating"))

# --- провал генерации виден
syn.generate_json = lambda *a, **k: None
STEPS.clear()
res, _ = syn.generate_guarded("t", "es", "s", [], [], None, [], SKILL_V,
                              on_step=collect)
check("провал объявлен шагом failed",
      res is None and [k for k, _ in STEPS][-1] == "failed")

# --- падение обработчика шага не роняет генерацию
RESP[:] = [{"title": "x" * 40, "highlights": "y", "dropped": []}]
syn.generate_json = lambda *a, **k: RESP.pop(0)


def broken(kind, **kw):
    raise RuntimeError("виджет умер")


res, _ = syn.generate_guarded("t", "es", "s", [], [], None, [], SKILL_V,
                              on_step=broken)
check("сломанный показ хода не ломает генерацию", res is not None)

# --- без обработчика всё работает как раньше
RESP[:] = [{"title": "x" * 40, "highlights": "y", "dropped": []}]
syn.generate_json = lambda *a, **k: RESP.pop(0)
res, _ = syn.generate_guarded("t", "es", "s", [], [], None, [], SKILL_V)
check("без обработчика генерация идёт", res is not None)

# --- перегенерация: старый результат не показывается
check("при флаге перегенерации карточка выходит до отрисовки результата",
      'if st.session_state.get(f"regen-{asin}-{mp}"):' in SRC
      and SRC.index('if st.session_state.get(f"regen-{asin}-{mp}"):')
      < SRC.index('res = st.session_state.get(f"res-{asin}-{mp}")'))
check("вместо него показывается, что идёт перегенерация",
      't("gen.regenerating")' in SRC)

# --- партия: числа, а не голый счётчик
check("в партии показываются сгенерированные и пропущенные",
      't("gen.batch", i=i, n=len(items), done=done' in SRC)
check("и текущий товар отдельной строкой",
      "line.caption(" in SRC)

# --- переводы на месте во всех трёх языках
from i18n import LANGS                                  # noqa: E402
keys = [k for k in LANGS["ru"] if k.startswith("gen.")]
check("ключи хода есть в трёх языках",
      all(set(keys) <= set(LANGS[l]) for l in ("ru", "uk", "en")))
check("шагов достаточно, чтобы описать весь путь", len(keys) >= 9)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
