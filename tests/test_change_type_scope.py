# -*- coding: utf-8 -*-
"""
tests/test_change_type_scope.py — правки разных полей не должны смешиваться.

`synthesis_changes` — одна таблица на ВСЕ поля листинга: тайтл, буллеты,
описание. Различает их `change_type`. Пока писался один тип, фильтр можно
было не ставить, и в двух местах его не было — в `synthesis.load_accepted`
и в `services/worklog`.

Сработает это ровно в тот день, когда примут первый буллет, и сработает
молча: карточка Синтеза покажет текст буллета как принятый тайтл, счётчик
длины посчитает «212/75», значок «тайтл принят» встанет товару, у которого
тайтл не трогали. Ошибка выглядит не как ошибка, а как чужая работа.

Поэтому проверяется не «есть ли фильтр в коде», а ПОВЕДЕНИЕ: в базе лежит
принятый буллет, и он не должен попасть ни в одно место, где ждут тайтл.

Вторая половина — про методологию. Областей в `synthesis_skill`
двенадцать, подключён пока тайтл; `load_skill` обязан уметь брать любую,
иначе для каждого нового поля появится своя копия загрузчика.

Запуск (pytest не нужен):  python tests/test_change_type_scope.py
"""
from __future__ import annotations

import pathlib
import re
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


T = pd.Timestamp
MP = "es"
ASIN = "B0BOTH"
TITLE = "Martillo Percutor SDS-Plus 1500W BH-20"
BULLET = ("MOTOR BRUSHLESS 20V: taladro atornillador inalámbrico con motor "
          "sin escobillas que dura más y calienta menos en trabajos largos")

# У одного и того же товара приняты и тайтл, и буллеты. Буллет принят
# ПОЗЖЕ — значит «последняя правка по паре» без фильтра вернёт его.
CHANGES = pd.DataFrame([
    dict(asin=ASIN, marketplace=MP, change_type="title_split",
         accepted_at=T("2026-09-01 10:00"), status="accepted",
         after_text=TITLE, after_len=len(TITLE), after_extra=None,
         coverage_score=88.0, model="claude-opus-5", skill_version=10,
         source="ai", before_text="было " * 20),
    dict(asin=ASIN, marketplace=MP, change_type="bullets",
         accepted_at=T("2026-09-05 12:00"), status="accepted",
         after_text=BULLET, after_len=len(BULLET), after_extra=None,
         coverage_score=81.0, model="claude-opus-5", skill_version=2,
         source="ai", before_text="было " * 20),
])
SNAP = pd.DataFrame([dict(
    asin=ASIN, marketplace=MP, sku_group="17557000", is_competitor=False,
    title="Dnipro-M BH-20 Martillo Percutor Rotativo SDS-Plus " * 3,
    fetched_at=T("2026-09-05"), ok=True, main_image=None, raw={},
    review_count=10, last_ok=True, last_fetch=T("2026-09-05"),
    red=1, amber=0, yellow=0, added_at=T("2026-08-01"))])
# без боли title_over_limit страница Синтеза останавливается на «нет
# кандидатов» и до методологии не доходит — очередь ей нужна
DIAG = pd.DataFrame([dict(
    asin=ASIN, marketplace=MP, sku_group="17557000",
    rule_id="title_over_limit", severity="red", pain="длинный тайтл",
    cause="c", action="a", money_impact=100.0, created_at=T("2026-09-05"),
    resolved_at=None, title=SNAP.iloc[0]["title"] if False else None,
    fetched_at=T("2026-09-05"), main_image=None)])
SKILLS = pd.DataFrame([
    dict(scope="common", skill_text="Общая часть.", version=5),
    dict(scope="title_split", skill_text="Правила тайтла.", version=10),
    dict(scope="bullets", skill_text="Правила буллетов.", version=2),
])

ASKED: list[str] = []


def fake_sql(sql, conn=None, params=None, **kw):
    s = " ".join(str(sql).split())
    if "FROM synthesis_skill" in s:
        ASKED.append(str((params or {}).get("scope")))
        scopes = {"common", (params or {}).get("scope")}
        return SKILLS[SKILLS["scope"].isin(scopes)].copy()
    if "FROM synthesis_changes" in s:
        df = CHANGES.copy()
        # фильтр применяет БАЗА — здесь повторяем её работу, чтобы
        # проверять поведение страницы, а не текст запроса
        m = re.search(r"change_type = '(\w+)'", s)
        if m:
            df = df[df["change_type"] == m.group(1)]
        if "before_text AS before_title" in s:
            df = df.rename(columns={"before_text": "before_title",
                                    "after_text": "after_title"})
            df["highlights"] = None
        return df
    if "FROM diagnosis" in s:
        # очередь Синтеза: пара с болью превышения лимита
        df = DIAG.copy()
        df["title"] = SNAP.iloc[0]["title"]
        return df
    if ("FROM listing_snapshots" in s or "FROM product_matrix" in s
            or "listing_latest" in s):
        return SNAP.copy()
    return pd.DataFrame()


pd.read_sql = fake_sql

import services.worklog as worklog                      # noqa: E402
import services.flatfile as ff                          # noqa: E402
# выгрузка здесь ни при чём: она и так фильтрует тип правки, а её
# раскладка по шаблонам требует своей фикстуры
ff.load_accepted_titles = lambda mps=None: pd.DataFrame()
from streamlit.testing.v1 import AppTest                # noqa: E402
import streamlit as st                                  # noqa: E402


def page(path="pages/synthesis.py"):
    st.cache_data.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    at.switch_page(path).run()
    return at


# --- 1. принятый буллет не подменяет принятый тайтл на экране
at = page()
body = " ".join([str(m.value) for m in at.markdown]
                + [str(c.value) for c in at.caption])
check("страница отрисована", not at.exception)
check("текст буллета на экран Синтеза не попал", BULLET[:40] not in body)

# --- 2. и не подменяет его в следе работы по товару.
# Здесь проверяем сам запрос: у worklog один большой SQL с тремя CTE,
# и фильтр обязан стоять в ТОЙ, что читает принятые правки, — иначе
# грепом по файлу это неотличимо от фильтра в соседнем блоке
_wl = (ROOT / "services/worklog.py").read_text(encoding="utf-8")
_c_block = _wl[_wl.index("c AS ("):_wl.index("g AS (")]
check("worklog берёт правки тайтла, а не последние по времени",
      "change_type = 'title_split'" in _c_block)

# --- 3. фильтр стоит в каждом чтении (INSERT не в счёт)
_no_filter = []
for _f in ("pages/synthesis.py", "services/worklog.py", "services/history.py",
           "services/flatfile.py"):
    _src = (ROOT / _f).read_text(encoding="utf-8")
    for _m in re.finditer(r"FROM synthesis_changes\b(.{0,400})", _src, re.S):
        if "change_type" not in _m.group(1):
            _no_filter.append(_f)
check(f"все чтения synthesis_changes фильтруют тип ({_no_filter or '—'})",
      not _no_filter)

# --- 4. методология берётся по области, а не жёстко по тайтлу
SRC = (ROOT / "pages/synthesis.py").read_text(encoding="utf-8")
check("load_skill принимает область", "def load_skill(scope: str" in SRC)
check("область уходит в запрос параметром",
      "scope IN ('common', %(scope)s)" in SRC)
check("страница Синтеза просит именно title_split",
      "title_split" in str(ASKED))

# --- 5. приёмка умеет писать тип, а не зашивает его в SQL
check("accept_change принимает change_type",
      "change_type: str = \"title_split\"" in SRC)
check("тип уходит параметром запроса, а не литералом",
      "VALUES (%s,%s,%s," in SRC and "'title_split',%s,%s" not in SRC)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
