# -*- coding: utf-8 -*-
"""
services/economics.py — экономика ASIN: выручка, трафик, конверсия.

Источник: listing_data.asin_economics (наполняется ноутбуком
Listing Suite Sync Economics из Sales & Traffic за 30 дней).

Зачем: приоритет проблем по деньгам, а не только по severity. Боль на
товаре с выручкой 4 100 в месяц важнее той же боли на товаре с 80.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from services.db import get_conn

# доля выручки, которой рискуем при каждом типе проблемы
# (консервативные оценки; не выдумка «impact», а прозрачный коэффициент)
RULE_RISK = {
    "out_of_stock": 1.00,        # товар недоступен — теряется всё
    "title_over_limit": 0.15,    # Amazon переписывает тайтл сам
    "no_aplus": 0.08,
    "few_images": 0.06,
    "no_video": 0.04,
    "low_reviews": 0.05,
    "no_shipping_template": 0.05,
    "low_ctr": 0.25,           # показывают, но не кликают —
                               # теряем четверть потенциала трафика
}


@st.cache_data(ttl=300)
def load_economics() -> pd.DataFrame:
    """Экономика по всем ASIN×MP за последние 30 дней."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT asin, marketplace,
                   sessions_30d, units_ordered_30d, revenue_30d,
                   conversion_rate, avg_price, buy_box_pct,
                   shipping_template, updated_at
            FROM asin_economics
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def econ_map(df: pd.DataFrame | None = None) -> dict:
    """(asin, marketplace) -> словарь метрик."""
    df = load_economics() if df is None else df
    if df.empty:
        return {}
    return {(r["asin"], r["marketplace"]): r.to_dict()
            for _, r in df.iterrows()}


def money_at_risk(rule_id: str, revenue_30d) -> float:
    """Сколько выручки под риском из-за конкретной проблемы."""
    try:
        rev = float(revenue_30d or 0)
    except (TypeError, ValueError):
        return 0.0
    return rev * RULE_RISK.get(rule_id, 0.03)


def fmt_money(v, suffix: str = "") -> str:
    try:
        val = float(v or 0)
    except (TypeError, ValueError):
        return "—"
    if val <= 0:
        return "—"
    if val >= 1000:
        return f"€{val:,.0f}".replace(",", " ") + suffix
    return f"€{val:.0f}{suffix}"


def fmt_conversion(v) -> str:
    try:
        val = float(v or 0)
    except (TypeError, ValueError):
        return "—"
    if val <= 0:
        return "—"
    # значение может прийти как доля (0.16) или как проценты (16.7)
    pct = val * 100 if val <= 1 else val
    return f"{pct:.1f}%".replace(".", ",")
