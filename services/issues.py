# -*- coding: utf-8 -*-
"""
services/issues.py — Amazon Issues: проблемы листингов из Seller Central.

Источник: listing_data.listing_issues — реплика из базы Кабинета,
синхронизируется ежедневно в 14:00. Берём только незакрытое
(resolved_at IS NULL). Рынки в реплике: ES, DE, IT, FR (MONITORED);
для остальных отсутствие проблем неотличимо от отсутствия данных —
это отдельное состояние «мониторинг не настроен», не «всё хорошо».

ВАЖНО ПРО ЦВЕТ: severity от Amazon недостоверен — EPR приходит как
WARNING и при этом снимает листинг с продажи, а ошибки языка атрибутов
помечены ERROR и ни на что не влияют. Единственный надёжный признак —
is_buyable. severity из реплики здесь нигде не участвует в выборе цвета.

Правила диагноза считаются В МОМЕНТ ПОКАЗА (build_pains, мерж в Диагнозе),
а не в автосборе: автосбор идёт в 13:00, реплика обновляется в 14:00 —
правила в автосборе брали бы вчерашние данные. В diagnosis эти боли
не пишутся, изменений на стороне Databricks не требуется.
"""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from i18n import t
from services.db import get_conn

# рынки, по которым Кабинет реально собирает Issues
MONITORED = {"es", "de", "it", "fr"}

# причины блокировки, у которых есть своя формулировка боли и действия;
# всё незнакомое уходит в generic
BLOCK_CAUSES = {
    "variant_conflict", "compliance_docs", "epr", "hazmat",
    "missing_image", "gpsr",
}


# ---------------------------------------------------------------- helpers

def _bool(v) -> bool | None:
    """True / False / None (нет данных). pd.isna, а не `if v` — правило 4."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return bool(v)


def _text(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return str(v).strip()


def _esc(s: str) -> str:
    """Текст Amazon уходит в HTML карточки боли — экранируем."""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _int(v) -> int | None:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
        return int(float(v))
    except (TypeError, ValueError):
        return None


def fmt_issue_date(v, with_year: bool = False) -> str:
    """first_seen -> «19.05» / «19.05.2026»; нет даты — прочерк."""
    ts = pd.to_datetime(v, errors="coerce")
    if pd.isna(ts):
        return "—"
    return ts.strftime("%d.%m.%Y" if with_year else "%d.%m")


def cause_label(cause: str | None) -> str:
    """Короткая подпись причины блокировки для плашки."""
    c = _text(cause) or "generic"
    key = f"issue.cause.{c}"
    val = t(key)
    return val if val != key else c


# ISO-дата в текстах Amazon: 2026-08-12T00:00:00.000Z
_ISO_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")


def extract_deadline(summary: dict) -> tuple[str, pd.Timestamp] | None:
    """Первый дедлайн из текстов Amazon по паре: (подпись кода, дата).

    Amazon пишет срок прямо в message ISO-датой; отдельного поля в реплике
    нет, поэтому вытаскиваем регуляркой."""
    for row in summary.get("rows") or []:
        m = _ISO_RE.search(row.get("message") or "")
        if not m:
            continue
        ts = pd.to_datetime(m.group(0), errors="coerce", utc=True)
        if not pd.isna(ts):
            return code_label(row.get("code")), ts
    return None


def code_label(code: str | None) -> str:
    """Подпись кода проблемы; незнакомый код показывается как есть."""
    c = _text(code)
    key = f"issue.code.{c}"
    val = t(key)
    return val if val != key else c


# ---------------------------------------------------------------- загрузка

@st.cache_data(ttl=300)
def load_issues() -> pd.DataFrame:
    """Незакрытые проблемы по всем ASIN×MP."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT sku, asin, marketplace, is_buyable, is_discoverable,
                   issue_code, severity, message, attribute_names,
                   first_seen, last_seen, had_sales_before, stock_qty,
                   suppression_cause
            FROM listing_issues
            WHERE resolved_at IS NULL
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def _summary(g: pd.DataFrame) -> dict:
    """Сводка по паре товар×рынок: ОДНА запись на пару, не на каждый код."""
    rows = []
    for _, r in g.iterrows():
        rows.append({
            "code": _text(r.get("issue_code")),
            "message": _text(r.get("message")),
            "attributes": _text(r.get("attribute_names")),
            "first_seen": r.get("first_seen"),
        })
    rows.sort(key=lambda x: str(x.get("code")))

    # is_buyable — признак листинга, в строках дублируется; блокирован,
    # если ХОТЬ одна строка говорит false (недоверие в сторону худшего)
    blocked = any(_bool(r.get("is_buyable")) is False for _, r in g.iterrows())

    # suppression_cause уже приоритезирован на стороне Кабинета
    cause = next((_text(r.get("suppression_cause"))
                  for _, r in g.iterrows()
                  if _text(r.get("suppression_cause"))), "")

    # had_sales_before: False только если это явно сказано; неизвестность
    # трактуем как «продавался», чтобы не занижать риск по незнанию
    flags = [_bool(r.get("had_sales_before")) for _, r in g.iterrows()]
    had_sales = True if any(f is True for f in flags) else (
        False if any(f is False for f in flags) else True)

    first_seen = pd.to_datetime(
        pd.Series([r["first_seen"] for r in rows]), errors="coerce").min()
    stock = next((_int(r.get("stock_qty")) for _, r in g.iterrows()
                  if _int(r.get("stock_qty")) is not None), None)
    sku = next((_text(r.get("sku")) for _, r in g.iterrows()
                if _text(r.get("sku"))), "")

    # первичное сообщение Amazon — самое раннее (обычно причина блокировки)
    with_msg = [r for r in rows if r["message"]]
    with_msg.sort(key=lambda x: str(pd.to_datetime(x["first_seen"],
                                                   errors="coerce")))
    message = with_msg[0]["message"] if with_msg else ""

    return {
        "state": "blocked" if blocked else ("warning" if rows else "none"),
        "cause": cause,
        "had_sales": had_sales,
        "first_seen": None if pd.isna(first_seen) else first_seen,
        "stock": stock,
        "sku": sku,
        "message": message,
        "codes": sorted({r["code"] for r in rows if r["code"]}),
        "rows": rows,
    }


def issues_map(df: pd.DataFrame | None = None) -> dict:
    """(asin, marketplace) -> сводка проблем."""
    df = load_issues() if df is None else df
    if df.empty:
        return {}
    out = {}
    for (asin, mp), g in df.groupby(["asin", "marketplace"]):
        s = _summary(g)
        # ASIN и рынок нужны в раскрытии плашки: у одного SKU на разных
        # рынках ASIN может отличаться — без него непонятно, что чинить
        s["asin"] = str(asin)
        s["marketplace"] = str(mp).lower()
        out[(str(asin), str(mp).lower())] = s
    return out


@st.cache_data(ttl=300)
def load_family() -> pd.DataFrame:
    """Состав семейств вариантов: все наши ASIN по sku_group × рынок.

    Именно из матрицы, а не из listing_issues: в реплике только листинги
    с незакрытыми проблемами, чистые варианты семейства там отсутствуют —
    знаменатель «заблокирован 1 из 4» из неё не получить."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            "SELECT sku_group, asin, marketplace FROM product_matrix "
            "WHERE is_competitor = FALSE",
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def family_map(imap: dict | None = None) -> dict:
    """(asin, marketplace) -> {"total": N, "blocked": K} по семейству
    sku_group на этом рынке. Только для семейств, где есть блокировки."""
    fam = load_family()
    if fam.empty:
        return {}
    imap = issues_map() if imap is None else imap
    out: dict = {}
    for (sku, mp), g in fam.groupby(["sku_group", "marketplace"]):
        mpl = str(mp).lower()
        asins = [str(a) for a in g["asin"]]
        blocked = [a for a in asins
                   if (imap.get((a, mpl)) or {}).get("state") == "blocked"]
        if not blocked:
            continue
        info = {"total": len(asins), "blocked": len(blocked)}
        for a in asins:
            out[(a, mpl)] = info
    return out


def asin_index(imap: dict | None = None) -> dict:
    """asin -> [(marketplace, сводка), ...] — для «худшего состояния»
    товара, живущего на нескольких рынках."""
    imap = issues_map() if imap is None else imap
    idx: dict = {}
    for (asin, mp), s in imap.items():
        idx.setdefault(asin, []).append((mp, s))
    rank = {"blocked": 0, "warning": 1, "none": 2}
    for asin in idx:
        idx[asin].sort(key=lambda x: rank.get(x[1]["state"], 9))
    return idx


def worst_state(entries: list) -> str:
    """blocked | warning | none по списку (mp, сводка)."""
    states = {s["state"] for _, s in entries or []}
    if "blocked" in states:
        return "blocked"
    if "warning" in states:
        return "warning"
    return "none"


# ---------------------------------------------------------------- диагноз

def build_pains(imap: dict | None = None) -> pd.DataFrame:
    """Виртуальные боли для Диагноза — считаются на лету, в diagnosis
    не пишутся (см. докстринг модуля про 13:00 vs 14:00).

    ОДНА боль на пару товар×рынок. is_buyable=false -> red по
    suppression_cause; исключение out_of_stock — по остаткам в Диагнозе
    уже есть своё правило, дубль об одном и том же не создаём.
    is_buyable=true при незакрытых проблемах -> yellow.
    """
    imap = issues_map() if imap is None else imap
    fam = family_map(imap)
    recs = []
    for (asin, mp), s in imap.items():
        if s["state"] == "none":
            continue
        if s["state"] == "blocked":
            if s["cause"] == "out_of_stock":
                continue
            cause_id = s["cause"] if s["cause"] in BLOCK_CAUSES else "generic"
            rule, sev = "amazon_blocked", "red"
            pain = t(f"pain.amazon_blocked.{cause_id}")
            action = t(f"action.amazon_blocked.{cause_id}")
        else:
            rule, sev = "amazon_warning", "yellow"
            pain = t("pain.amazon_warning")
            action = t("action.amazon_warning")

        parts = [t("issue.since_date", date=fmt_issue_date(s["first_seen"], with_year=True))]
        if s["stock"] is not None:
            parts.append(t("issue.stock_n", n=s["stock"]))
        if s["codes"]:
            parts.append(", ".join(f"{c} · {code_label(c)}" for c in s["codes"]))
        if not s["had_sales"]:
            parts.append(t("issue.never_sold"))
        cause_line = " · ".join(parts)
        if s["message"]:
            cause_line += f" — {_esc(s['message'])}"

        # живые варианты в семействе: часть трафика перетекает внутрь
        # семейства, риск блокировки ниже (economics.BLOCKED_WITH_ALIVE_RISK)
        f = fam.get((asin, mp))
        family_alive = (f["blocked"] < f["total"]) if f else False

        recs.append({
            "sku_group": s["sku"] or asin,
            "asin": asin,
            "marketplace": mp,
            "rule_id": rule,
            "severity": sev,
            "pain": pain,
            "cause": cause_line,
            "action": action,
            "money_impact": None,
            "created_at": pd.to_datetime(s["first_seen"], errors="coerce",
                                         utc=True),
            "_had_sales": s["had_sales"],
            "_family_alive": family_alive,
        })
    return pd.DataFrame(recs)
