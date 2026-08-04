# -*- coding: utf-8 -*-
"""
services/search.py — сводка Brand Analytics по товарам.

Отвечает на вопрос «как товар находят»: сколько запросов собрано, каков
суммарный спрос, какую долю показов мы забираем, сколько покупок пришло
из поиска. Источник — listing_data.sqp_reports (загрузчик SQP Loader).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from services.db import get_conn

# пороги правила «показывают, но не кликают»
CTR_MIN_IMPRESSIONS = 200     # ниже этого выборка слишком мала для вывода
CTR_WARN = 0.3                # % — ниже считаем проблемой карточки


@st.cache_data(ttl=300)
def load_search_summary(weeks: int = 4) -> pd.DataFrame:
    """Сводка поиска по каждому ASIN×MP за последние недели."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT asin, marketplace,
                   count(DISTINCT search_query)      AS queries,
                   sum(search_query_volume)          AS demand,
                   sum(impressions_asin)             AS impressions,
                   sum(impressions_total)            AS impressions_market,
                   sum(clicks_asin)                  AS clicks,
                   sum(purchases_asin)               AS purchases,
                   max(reporting_date)               AS last_week
            FROM sqp_reports
            WHERE reporting_date >= current_date - %(days)s
            GROUP BY asin, marketplace
            """,
            conn, params={"days": weeks * 7},
        )
        conn.close()
        if df.empty:
            return df
        df["imp_share"] = (df["impressions"] / df["impressions_market"]
                           .replace(0, pd.NA) * 100).astype(float)
        df["ctr"] = (df["clicks"] / df["impressions"].replace(0, pd.NA)
                     * 100).astype(float)
        return df
    except Exception:
        return pd.DataFrame()


def search_map(weeks: int = 4) -> dict:
    df = load_search_summary(weeks)
    if df.empty:
        return {}
    return {(r["asin"], r["marketplace"]): r.to_dict()
            for _, r in df.iterrows()}


def fmt_int(v) -> str:
    try:
        return f"{int(v):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


def fmt_pct(v, digits: int = 2) -> str:
    try:
        val = float(v)
    except (TypeError, ValueError):
        return "—"
    if pd.isna(val):
        return "—"
    return f"{val:.{digits}f}%".replace(".", ",")


def ctr_state(s: dict | None) -> str:
    """ok | warn | none — для подсветки чипа CTR."""
    if not s:
        return "none"
    imp = s.get("impressions") or 0
    ctr = s.get("ctr")
    if imp < CTR_MIN_IMPRESSIONS or ctr is None or pd.isna(ctr):
        return "none"
    return "warn" if float(ctr) < CTR_WARN else "ok"
