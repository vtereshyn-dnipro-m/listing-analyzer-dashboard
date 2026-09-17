# -*- coding: utf-8 -*-
"""
tests/test_matrix_input.py — ввод пар в Матрицу: ASIN не выдаёт себя за SKU.

Парсер пачки терпим к форме строки — «sku, asin, mp», голый ASIN,
URL Amazon. При голом ASIN он писал `sku or asin`: ASIN попадал
в sku_group, и в Каталоге, выгрузке и группировках Синтеза у товара
стоял «sku B0G4S9SJ3M». Подмена неотличима от правды — SKU и ASIN
одинаково выглядят кодами.

Проверяются три вещи:
  · голый ASIN даёт ПУСТОЙ sku, а не ASIN;
  · вставка берёт SKU из зеркала каталога (catalog_source), а пустой
    повторный ввод не затирает уже известный;
  · колонка NOT NULL, поэтому «неизвестно» — пустая строка, не NULL.

Запуск (pytest не нужен):  python tests/test_matrix_input.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import services.db as db                               # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


# --- 1. парсер: все формы, и ни одна не подставляет ASIN в SKU
rows = db.parse_asin_lines("""
# комментарий
B0G4S9SJ3M
54225000, B0G4S9SJ3M, es
https://www.amazon.de/dp/B0GZVYHHS3
78740000, B0GZVYHHS3, it, конкурент
""")
by = {(a, mp): (sku, comp) for sku, a, mp, comp in rows}
check("голый ASIN — sku пустой, не ASIN", by[("B0G4S9SJ3M", "com")] == ("", False))
check("URL Amazon — рынок из домена, sku пустой", by[("B0GZVYHHS3", "de")] == ("", False))
check("явный sku сохраняется", by[("B0G4S9SJ3M", "es")] == ("54225000", False))
check("конкурент помечен", by[("B0GZVYHHS3", "it")] == ("78740000", True))
check("ASIN нигде не стал SKU", all(sku != a for sku, a, _, _ in rows))


# --- 2. вставка: SKU из зеркала, пустое не затирает известное
class _Cur:
    seen: list = []

    def executemany(self, sql, params):
        _Cur.seen.append((sql, list(params)))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn:
    def cursor(self):
        return _Cur()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


n = db.add_matrix_rows(_Conn(), rows)
sql, params = _Cur.seen[-1]
check("вставлены все четыре", n == 4 and len(params) == 4)
check("SKU при пустом вводе берётся из зеркала каталога",
      "FROM catalog_source" in sql and "NULLIF(%(sku)s, '')" in sql)
check("нет и в зеркале — пустая строка, не ASIN и не NULL",
      "                     '')" in sql and "%(asin)s, %(mp)s" in sql)
check("повтор с пустым sku не затирает известный",
      "COALESCE(NULLIF(EXCLUDED.sku_group, ''), product_matrix.sku_group)" in sql)
check("в параметрах ASIN не подставлен в sku",
      all(p["sku"] != p["asin"] for p in params))
_code = "\n".join(ln for ln in (ROOT / "services/db.py").read_text(encoding="utf-8")
                  .split("def parse_asin_lines")[1].split("\ndef ")[0].splitlines()
                  if not ln.strip().startswith("#"))
check("в коде парсера (не в комментариях) нет `or asin`", "or asin" not in _code)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
