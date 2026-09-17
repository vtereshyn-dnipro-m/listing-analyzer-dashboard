# -*- coding: utf-8 -*-
"""
tests/test_resolved_pains.py — закрытая боль не имеет права вернуться.

Боль закрывается, когда сбор её больше не находит, но запись остаётся
в `diagnosis` с проставленным `resolved_at`. Запросы фильтра не ставили,
брали последнюю запись по паре и правилу — и закрытое возвращалось
на экран вместе с живым: товар с готовым A+ показывал «Нет A+ контента»,
а тайтл в 62 символа при лимите 75 — «Amazon перепишет сам».

Дороже самой ошибки то, что она не только на экране. Деньги под риском
и счётчики болей считаются по ТОМУ ЖЕ набору, поэтому завышенным было
всё: и «€10 517 под риском», и число товаров, требующих внимания,
и очередь Синтеза.

Отдельная проверка — про обратную сторону. Пустой ответ на этот запрос
означает «проблем нет», и страница рисует зелёное «✓ N здоровых
товаров». При недоступной базе она тем самым УТВЕРЖДАЕТ, что всё
в порядке, — не молчит о сбое, а говорит противоположное правде.

Запуск (pytest не нужен):  python tests/test_resolved_pains.py
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
LIVE, DONE = "B0LIVE", "B0DONE"

# У B0DONE обе боли закрыты — ровно случай B0DZPC9YFZ: A+ собран,
# тайтл уложен, а записи в таблице остались.
PAINS = pd.DataFrame([
    dict(asin=LIVE, marketplace=MP, rule_id="no_aplus", severity="amber",
         pain="Нет A+ контента", cause="c", action="a", money_impact=500.0,
         created_at=T("2026-08-22"), resolved_at=None),
    dict(asin=DONE, marketplace=MP, rule_id="no_aplus", severity="amber",
         pain="Нет A+ контента", cause="c", action="a", money_impact=700.0,
         created_at=T("2026-08-22"), resolved_at=T("2026-08-26")),
    dict(asin=DONE, marketplace=MP, rule_id="title_over_limit", severity="red",
         pain="Тайтл 120 симв.", cause="c", action="a", money_impact=900.0,
         created_at=T("2026-08-22"), resolved_at=T("2026-08-26")),
])
SNAP = pd.DataFrame([
    dict(asin=a, marketplace=MP, sku_group=f"1755700{i}", is_competitor=False,
         title="Martillo Percutor " * 4, fetched_at=T("2026-09-03"), ok=True,
         main_image=None, raw={}, review_count=10, last_ok=True,
         last_fetch=T("2026-09-03"), red=1, amber=0, yellow=0,
         added_at=T("2026-08-01"))
    for i, a in enumerate((LIVE, DONE))])
ECON = pd.DataFrame([
    dict(asin=a, marketplace=MP, revenue_30d=10000.0, sessions_30d=100,
         conversion=0.1, buy_box_pct=100.0, shipping_template="")
    for a in (LIVE, DONE)])

# Боли из Кабинета (listing_issues) читаются ОТДЕЛЬНЫМ запросом и
# в diagnosis не пишутся. Из-за них страница не останавливается на
# «данных нет» при сбое чтения диагноза — и доходит до блока «здоровых»,
# считая здоровье по неполному набору болей. Ровно этот случай и надо
# заперёть, поэтому в фикстуре Issues есть.
ISSUES = pd.DataFrame([dict(
    sku="17557000", asin=LIVE, marketplace=MP, is_buyable=False,
    is_discoverable=True, issue_code="100530", severity="WARNING",
    message="Attribute missing", attribute_names="item_name",
    first_seen=T("2026-09-01"), last_seen=T("2026-09-03"),
    had_sales_before=True, stock_qty=0, suppression_cause="out_of_stock",
    asin_state="SUPPRESSED")])

SEEN: list[str] = []
MODE = {"fail": False}


def fake_sql(sql, conn=None, **kw):
    s = " ".join(str(sql).split())
    if "FROM diagnosis" in s:
        SEEN.append(s)
        if MODE["fail"]:
            raise RuntimeError("connection refused")
        # фильтр применяет БАЗА — здесь повторяем её работу, чтобы
        # проверять поведение страницы, а не текст запроса
        df = PAINS.copy()
        if "resolved_at IS NULL" in s:
            df = df[df["resolved_at"].isna()]
        return df
    if "FROM listing_issues" in s:
        return ISSUES.copy()
    if "FROM asin_economics" in s:
        return ECON.copy()
    # счётчик собранных пар: без него healthy = 0, и проверка «зелёного
    # при сбое нет» проходила бы сама собой, ничего не сторожа
    if "count(DISTINCT" in s and "listing_snapshots" in s:
        return pd.DataFrame([{"n": 2}])
    if "count(*)" in s and "product_matrix" in s:
        return pd.DataFrame([{"n": 2}])
    if ("FROM listing_snapshots" in s or "FROM product_matrix" in s
            or "listing_latest" in s):
        return SNAP.copy()
    return pd.DataFrame()


pd.read_sql = fake_sql
from services.economics import money_at_risk            # noqa: E402
from streamlit.testing.v1 import AppTest                # noqa: E402


def page(path="pages/dashboard.py"):
    import streamlit as st
    st.cache_data.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    at.switch_page(path).run()
    return at


def texts(at) -> str:
    return " ".join([str(m.value) for m in at.markdown]
                    + [str(c.value) for c in at.caption]
                    + [str(e.value) for e in at.error])


# --- 1. фильтр стоит во всех запросах, кроме дельты
SQL_FILES = ("pages/dashboard.py", "pages/synthesis.py", "pages/catalog.py",
             "pages/guide.py", "pages/matrix_setup.py")
_unfiltered = []
for _f in SQL_FILES:
    _src = (ROOT / _f).read_text(encoding="utf-8")
    for _m in re.finditer(r"(FROM diagnosis\b[^\"']*?)(?=\"\"\"|\Z)", _src, re.S):
        _chunk = _m.group(1)[:600]
        if "resolved_at IS NULL" not in _chunk:
            _unfiltered.append(f"{_f}: …{_chunk[:60].strip()}…")
# дельта живёт без фильтра намеренно: ей нужна история двух прогонов
_unfiltered = [u for u in _unfiltered if "run_day" not in u and "runs" not in u]
check(f"запросы к diagnosis фильтруют закрытые ({len(_unfiltered)} без фильтра)",
      not _unfiltered)
check("исключение для дельты объяснено в коде",
      "Дельте нужна история" in
      (ROOT / "pages/dashboard.py").read_text(encoding="utf-8"))

# --- 2. закрытая боль не попадает на экран и в числа
MODE["fail"] = False
at = page()
body = texts(at)
check("страница отрисована", not at.exception)
check("закрытая боль не показана", DONE not in body)
check("живая боль показана", LIVE in body)

# Деньги под риском — из шапки, а не «любое число с евро» на странице:
# выручка товара тоже печатается с евро, и проверка ловила бы её.
# У обоих товаров выручка одинаковая, поэтому закрытая боль удвоила бы
# сумму — проверяем ЧИСЛО, а не наличие подписи.
_risk_html = next((str(m.value) for m in at.markdown
                   if "color:#E8590C;font-weight:700" in str(m.value)), "")
_risk = re.sub(r"\D", "", re.search(r"€([\d\s\u2009]+)", _risk_html).group(1)) \
    if re.search(r"€([\d\s\u2009]+)", _risk_html) else ""
# по товару берётся МАКСИМУМ из его правил, а не сумма: боли
# пересекаются. У живого товара их две — своя и из Кабинета
_expect = int(max(money_at_risk("no_aplus", 10000.0),
                  money_at_risk("amazon_blocked", 10000.0)))
check(f"деньги под риском считаются по живому товару "
      f"(в шапке {_risk or '—'}, ждём {_expect}; закрытые дали бы больше)",
      _risk.isdigit() and int(_risk) == _expect)

# --- 3. Синтез: очередь тоже не тянет закрытые
_syn = (ROOT / "pages/synthesis.py").read_text(encoding="utf-8")
check("очередь Синтеза берёт только открытые боли",
      "d.rule_id = 'title_over_limit'" in _syn
      and "AND d.resolved_at IS NULL" in _syn)

# --- 4. сбой чтения не должен выглядеть как здоровье
MODE["fail"] = True
at = page()
body = texts(at)
check("при сбое чтения страница жива", not at.exception)
check("сбой назван сбоем, а не отсутствием данных",
      any("прочитать диагноз" in str(e.value) for e in at.error))
# «✓ N здоровых» ищем по самой плашке, а не по слову: слово «здоровье»
# есть и в тексте ошибки, и проверка проходила бы сама собой
_healthy_badge = [m for m in at.markdown if "#2F6B3A" in str(m.value)
                  and "✓" in str(m.value)]
check("зелёной плашки «N здоровых товаров» при сбое нет",
      not _healthy_badge)

print()
print("ИТОГ:", "все проверки прошли" if not FAILS
      else f"{len(FAILS)} провалов: {FAILS}")
sys.exit(1 if FAILS else 0)
