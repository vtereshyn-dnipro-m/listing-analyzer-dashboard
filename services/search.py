# -*- coding: utf-8 -*-
"""
services/search.py — поисковая сводка ASIN по Brand Analytics SQP.

Источник: listing_data.sqp_reports (наполняется ноутбуком из Search Query
Performance). Здесь — только агрегат за 4 недели для Каталога: по скольким
запросам товар вообще виден, каков суммарный спрос, какую долю показов мы
забираем, кликают ли по нам и покупают ли.

Отличие от services/seo.py: там пофразовая разметка для генерации тайтла,
здесь одна строка на товар для витрины. Обе читают одну таблицу.

CTR считается как clicks_asin / impressions_asin. Судить о нём можно только
при достаточном числе показов: у молодого листинга 3 клика из 12 показов —
это шум, а не 25% CTR.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from services.db import get_conn, get_engine
from services.settings import get_float

WEEKS = 4                     # окно сводки
MIN_IMPRESSIONS_FOR_CTR = 100  # меньше — выборка не показательна, состояние «нет данных»
CTR_MIN_DEFAULT = 0.3          # %, порог «кликают»; правится через app_settings


@st.cache_data(ttl=300)
def load_search(weeks: int = WEEKS) -> pd.DataFrame:
    """Сводка SQP по всем ASIN×MP за последние N недель.

    Агрегация двухуровневая: сначала по запросу (volume — характеристика
    запроса, его надо брать максимумом за период, а не суммой недель),
    потом по товару.
    """
    try:
        df = pd.read_sql(
            """
            WITH q AS (
                SELECT asin, marketplace, search_query,
                       max(search_query_volume) AS volume,
                       sum(impressions_asin)    AS imp_asin,
                       sum(impressions_total)   AS imp_total,
                       sum(clicks_asin)         AS clicks,
                       sum(purchases_asin)      AS purchases
                FROM sqp_reports
                WHERE reporting_date >= current_date - %(days)s
                GROUP BY asin, marketplace, search_query
            )
            SELECT asin, marketplace,
                   count(*)                                   AS queries,
                   sum(volume)                                AS demand,
                   sum(imp_asin)                              AS impressions,
                   sum(imp_total)                             AS impressions_total,
                   sum(clicks)                                AS clicks,
                   sum(purchases)                             AS purchases,
                   (100.0 * sum(imp_asin)
                          / NULLIF(sum(imp_total), 0))::float8 AS imp_share,
                   (100.0 * sum(clicks)
                          / NULLIF(sum(imp_asin), 0))::float8  AS ctr
            FROM q
            GROUP BY asin, marketplace
            """,
            get_engine(), params={"days": weeks * 7},
        )
        return df
    except Exception:
        return pd.DataFrame()


def search_map(df: pd.DataFrame | None = None) -> dict:
    """(asin, marketplace) -> словарь поисковых метрик."""
    df = load_search() if df is None else df
    if df.empty:
        return {}
    return {(r["asin"], r["marketplace"]): r.to_dict()
            for _, r in df.iterrows()}


def _num(v) -> float | None:
    """Число или None. pd.isna, а не `if v`: ноль — валидное значение,
    а NaN истинный и роняет форматирование."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def fmt_int(v) -> str:
    """Целое с разделителем тысяч: 12 400. Нет данных — прочерк."""
    n = _num(v)
    if n is None:
        return "—"
    return f"{int(round(n)):,}".replace(",", " ")


def fmt_pct(v) -> str:
    """Процент с запятой: 1,4%. Нет данных — прочерк."""
    n = _num(v)
    if n is None:
        return "—"
    return f"{n:.1f}%".replace(".", ",")


def ctr_state(sr: dict | None) -> str:
    """Состояние CTR для чипа: ok | warn | none.

    none — показов слишком мало, чтобы судить (или SQP по товару нет);
    warn — показывают, но не кликают: это боль трафика, а не контента.
    """
    if not sr:
        return "none"
    impressions = _num(sr.get("impressions")) or 0
    ctr = _num(sr.get("ctr"))
    if ctr is None or impressions < MIN_IMPRESSIONS_FOR_CTR:
        return "none"
    return "ok" if ctr >= get_float("threshold.min_ctr", CTR_MIN_DEFAULT) else "warn"
