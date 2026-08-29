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
    "empty_keywords": 0.10,    # не индексируемся по синонимам
    "few_attributes": 0.05,    # выпадаем из фильтров покупателя
    "hard_to_scan": 0.06,      # тайтл не цепляет взгляд в выдаче
    "low_ctr": 0.25,           # показывают, но не кликают —
                               # теряем четверть потенциала трафика
    "amazon_blocked": 1.00,    # листинг снят с продажи — теряется всё
    "amazon_fba_out": 0.20,    # FBA пуст, FBM живой: теряем Prime
                               # и скорость доставки, но не продажи целиком
    "amazon_warning": 0.05,    # предупреждение Amazon: риск снятия есть,
                               # но товар продаётся — ниже fba_out
}

# товар с had_sales_before = false — незапущенная карточка, а не поломка:
# «теряем выручку» по нему вводит в заблуждение, риск занижается
NEVER_SOLD_RISK = 0.05

# заблокирован, но в семействе есть живые варианты: покупатель видит на
# странице соседние и часть трафика перетекает внутрь семейства
BLOCKED_WITH_ALIVE_RISK = 0.40


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


def money_at_risk(rule_id: str, revenue_30d, had_sales: bool = True,
                  family_alive: bool | None = None) -> float:
    """Сколько выручки под риском из-за конкретной проблемы.

    family_alive=True (amazon_blocked при живых вариантах в семействе)
    снижает 1.00 -> BLOCKED_WITH_ALIVE_RISK. had_sales=False (товар
    никогда не продавался) занижает до NEVER_SOLD_RISK независимо
    от правила."""
    rev = num(revenue_30d)
    coef = risk_coef(rule_id)
    if coef is None:
        return 0.0          # правило без коэффициента денег не приносит
    if rule_id == "amazon_blocked" and family_alive is True:
        coef = BLOCKED_WITH_ALIVE_RISK
    if had_sales is False:
        coef = NEVER_SOLD_RISK
    return rev * coef


def num(v, default: float = 0.0) -> float:
    """Число из значения БД. `float(x or 0)` здесь не годится: NaN в Python
    ИСТИНЕН, поэтому `or` его пропускает и наружу выходит NaN, а не ноль.
    Дальше NaN тихо расползается — в сортировку, в суммы, в деньги."""
    try:
        if v is None or pd.isna(v):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


# Правила без коэффициента. Молчаливый дефолт 0.03 назначал деньги под
# риском правилу, для которого коэффициент никто не выбирал, — а цифра
# в деньгах выглядит одинаково убедительно, назначена она или выдумана.
# Теперь незнакомое правило денег не приносит, а его имя копится здесь,
# чтобы страница сказала об этом вслух.
_UNKNOWN_RULES: set[str] = set()


def unknown_rules() -> set[str]:
    """Правила, встреченные без коэффициента риска."""
    return set(_UNKNOWN_RULES)


def risk_coef(rule_id: str) -> float | None:
    """Коэффициент правила или None, если он не задан."""
    coef = RULE_RISK.get(rule_id)
    if coef is None:
        _UNKNOWN_RULES.add(str(rule_id))
    return coef


def fmt_money(v, suffix: str = "") -> str:
    val = num(v)
    if val <= 0:
        return "—"
    if val >= 1000:
        return f"€{val:,.0f}".replace(",", " ") + suffix
    return f"€{val:.0f}{suffix}"


def fmt_conversion(v) -> str:
    val = num(v)
    if val <= 0:
        return "—"
    # значение может прийти как доля (0.16) или как проценты (16.7)
    pct = val * 100 if val <= 1 else val
    return f"{pct:.1f}%".replace(".", ",")
