# -*- coding: utf-8 -*-
"""
tests/test_no_deprecations.py — лог не должен зарастать предупреждениями.

Смысл не в аккуратности. Предупреждения шли на каждый запрос и на каждую
таблицу, и в этом шуме не видно настоящих ошибок — а настоящие ошибки
в этом проекте стоили часов диагностики.

Две штуки:

1. `use_container_width` объявлен устаревшим, дедлайн был 31.12.2025 —
   параметр могут выключить в любом обновлении Streamlit, и тогда
   таблицы и картинки поедут молча.
2. pandas официально поддерживает только SQLAlchemy-подключения. С голым
   psycopg2 он работает, но предупреждает на каждый вызов.

Проверки грепом по исходникам намеренно: важно не «работает», а «нигде
не осталось», и одно возвращённое место обратно засоряет лог.

Отдельно проверяется, что pandas через движок действительно молчит —
остальные тесты подменяют pd.read_sql и этого бы не увидели.

Запуск (pytest не нужен):  python tests/test_no_deprecations.py
"""
from __future__ import annotations

import pathlib
import re
import sys
import tempfile
import warnings

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


CODE = (sorted((ROOT / "pages").glob("*.py"))
        + sorted((ROOT / "services").glob("*.py"))
        + sorted((ROOT / "components").glob("*.py")))

# --- 1. устаревший параметр ширины
hits = [f"{p.relative_to(ROOT)}:{i}"
        for p in CODE
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if "use_container_width" in ln]
check(f"use_container_width нигде нет ({hits or '—'})", not hits)

width_uses = sum(p.read_text(encoding="utf-8").count('width="stretch"')
                 for p in CODE)
check(f"на замену пришло width=\"stretch\" ({width_uses} мест)",
      width_uses >= 14)

# --- 2. чтения через движок, а не через голое соединение
raw_reads = []
for p in CODE:
    src = p.read_text(encoding="utf-8")
    for m in re.finditer(r"pd\.read_sql\((?:[^()]|\([^()]*\))*?\)", src, re.S):
        frag = m.group(0)
        if re.search(r",\s*conn\b", frag):
            raw_reads.append(f"{p.relative_to(ROOT)}:"
                             f"{src[:m.start()].count(chr(10)) + 1}")
check(f"pd.read_sql нигде не получает голое соединение ({raw_reads or '—'})",
      not raw_reads)

engine_reads = sum(len(re.findall(r"pd\.read_sql\(", p.read_text(encoding="utf-8")))
                   for p in CODE)
check(f"чтения остались на месте ({engine_reads} вызовов)", engine_reads >= 20)

# --- 3. сам движок
import services.db as db                                # noqa: E402

src_db = (ROOT / "services/db.py").read_text(encoding="utf-8")
check("get_engine существует", hasattr(db, "get_engine"))
check("движок строится поверх нашего get_conn, а не поверх строки подключения",
      "creator=get_conn" in src_db)
check("пул отключён — токен Lakebase живёт около часа",
      "NullPool" in src_db)
check("движок кэшируется как ресурс, а не пересоздаётся на каждый запрос",
      "@st.cache_resource" in src_db)
check("sqlalchemy объявлена в зависимостях",
      "sqlalchemy" in (ROOT / "requirements.txt").read_text(encoding="utf-8"))

# --- 4. pandas через движок действительно молчит
from sqlalchemy import create_engine                     # noqa: E402
from sqlalchemy.pool import NullPool                     # noqa: E402

# файл, а не :memory: — с NullPool каждое соединение новое, и таблица
# в памяти исчезла бы вместе с предыдущим. NullPool оставлен намеренно:
# он такой же, как у нашего движка
_tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
_tmp.close()
eng = create_engine(f"sqlite:///{_tmp.name}", poolclass=NullPool)
with eng.begin() as c:
    from sqlalchemy import text
    c.execute(text("CREATE TABLE t (a INTEGER, b TEXT)"))
    c.execute(text("INSERT INTO t VALUES (1, 'x'), (2, NULL)"))

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    df = pd.read_sql("SELECT a, b FROM t ORDER BY a", eng)
noisy = [str(x.message) for x in w
         if "SQLAlchemy" in str(x.message) or "DBAPI2" in str(x.message)]
check(f"чтение через движок не предупреждает ({noisy or '—'})", not noisy)
check("и данные приходят те же", len(df) == 2 and list(df.columns) == ["a", "b"])
check("NULL остаётся распознаваемым как пусто", bool(pd.isna(df["b"].iloc[1])))

pathlib.Path(_tmp.name).unlink(missing_ok=True)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
