# -*- coding: utf-8 -*-
"""
tests/test_silent_failures.py — сбой не должен выглядеть как «данных нет».

Четыре тихих отказа одного класса за неделю обошлись дороже всех остальных
поломок вместе. Здесь заперты три из них, найденные аудитом.

1. САМЫЙ ДОРОГОЙ. Сбой чтения SQP превращал генерацию в работу вслепую:
   `keep=[]`, `forbid=[]`, проверка `keeps_all` на пустом списке проходит
   сама собой, тайтлы получаются в лимите и с зелёными галочками — а
   поискового веса в них нет. Обнаружилось бы через недели по продажам.
   Теперь партия такой товар ПРОПУСКАЕТ и называет причину.

2. `float(x or 0)` не даёт нуля на NaN: NaN истинный, `or` его пропускает.
   Наружу выходил NaN и расползался в суммы и сортировки, а `int(NaN or 0)`
   падал с ValueError.

3. Правило без коэффициента риска получало 3% выручки — цифру, которую
   никто не выбирал. Теперь оно не приносит денег, а имя правила копится
   для предупреждения.

Запуск (pytest не нужен):  python tests/test_silent_failures.py
"""
from __future__ import annotations

import pathlib
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


NAN = float("nan")

# ---------------------------------------------------------------- 2 и 3
import services.economics as ec                         # noqa: E402

check("num(NaN) — ноль, а не NaN", ec.num(NAN) == 0.0)
check("num(None) — ноль", ec.num(None) == 0.0)
check("num('') — ноль", ec.num("") == 0.0)
check("num(12.5) не портит нормальное число", ec.num(12.5) == 12.5)
check("int(num(NaN)) не падает", int(ec.num(NAN)) == 0)
check("старый приём действительно ломался", str(float(NAN or 0)) == "nan")

check("известное правило даёт свой коэффициент",
      ec.risk_coef("out_of_stock") == 1.00)
check("незнакомое правило коэффициента НЕ получает",
      ec.risk_coef("brand_new_rule") is None)
check("и попадает в список для предупреждения",
      "brand_new_rule" in ec.unknown_rules())
check("деньги по незнакомому правилу не начисляются",
      ec.money_at_risk("brand_new_rule", 10000) == 0.0)
check("по известному — начисляются",
      ec.money_at_risk("title_over_limit", 10000) == 1500.0)
check("NaN в выручке не даёт NaN в деньгах",
      ec.money_at_risk("title_over_limit", NAN) == 0.0)

check("fmt_money(NaN) — прочерк, а не «nan»", ec.fmt_money(NAN) == "—")
check("fmt_conversion(NaN) — прочерк", ec.fmt_conversion(NAN) == "—")

# ---------------------------------------------------------------- 1
import services.seo as seo                              # noqa: E402


class _FailConn:
    def close(self):
        pass


def sqp_fails(*a, **k):
    raise RuntimeError("connection refused")


services.db.get_conn = lambda: _FailConn()
seo.get_conn = lambda: _FailConn()
pd.read_sql = sqp_fails
seo.load_sqp.clear()
df = seo.load_sqp("B0AAA", "es")
check("при сбое таблица фраз пуста", df.empty)
check("но причина сбоя сохранена",
      "connection refused" in (seo.sqp_error() or ""))

pd.read_sql = lambda *a, **k: pd.DataFrame(
    columns=["search_query", "volume", "impressions", "clicks",
             "purchases", "imp_share"])
seo.load_sqp.clear()
empty = seo.load_sqp("B0BBB", "es")
check("при честно пустом ответе таблица тоже пуста", empty.empty)
check("и ошибка сброшена — «нет данных» не путается со сбоем",
      seo.sqp_error() is None)

# --- партия: на сбое SQP товар пропускается, а не генерируется вслепую
import types                                            # noqa: E402

pd.read_sql = lambda *a, **k: pd.DataFrame()
src = (ROOT / "pages/synthesis.py").read_text(encoding="utf-8")
syn = types.ModuleType("syn")
syn.__dict__["__name__"] = "syn"
exec(compile(src[:src.index("with tab_queue:")], "syn", "exec"), syn.__dict__)

GENERATED: list = []
syn.generate_guarded = lambda *a, **k: (
    GENERATED.append(a) or ({"title": "T", "highlights": "H", "dropped": []},
                            {"attempts": 1}))
syn.build_keyword_table = lambda *a, **k: pd.DataFrame()
syn.save_draft = lambda *a, **k: True
syn.st.session_state.clear()

ITEMS = [{"r": {"asin": "B0AAA", "marketplace": "es",
                "title": "Título muy largo " * 6}, "draft": {}, "risk": 0.0}]

syn.sqp_error = lambda: "RuntimeError: connection refused"
out = syn.batch_generate(ITEMS, "методика", 7)
check("при сбое SQP генерация НЕ запускалась", not GENERATED)
check("товар посчитан как несостоявшийся", out["failed"] == 1)
check("причина названа в списке ошибок",
      out["errors"] and "connection refused" in out["errors"][0])
check("и сказано, чем это опасно",
      out["errors"] and "без обязательных фраз" in out["errors"][0])

GENERATED.clear()
syn.sqp_error = lambda: None
out2 = syn.batch_generate(ITEMS, "методика", 7)
check("а при честном отсутствии SQP генерация идёт", len(GENERATED) == 1)
check("и товар сохранён", out2["done"] == 1)

# ---------------------------------------------------------------- мёртвый код
db_src = (ROOT / "services/db.py").read_text(encoding="utf-8")
check("ensure_all_schemas удалён", "def ensure_all_schemas" not in db_src)
check("и не осталось ссылок на несуществующий services.diagnose",
      "services.diagnose" not in db_src)
check("правило про миграции переписано на фактическое",
      "migrations/" in db_src and "Databricks" in db_src)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
