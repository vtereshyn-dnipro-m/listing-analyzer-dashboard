# -*- coding: utf-8 -*-
"""
services/attributes.py — карточка товара со стороны каталога Amazon.

Источник: listing_data.listing_attributes (наполняется ноутбуком из Listings
Items API). Здесь не контент, который видит покупатель, а то, по чему Amazon
раскладывает товар: тип товара, browse node, заполненность атрибутов,
generic_keyword, буллеты, описание.

Зачем: пустые атрибуты не видны глазом на листинге, но выбрасывают товар из
фильтров покупателя, а пустой generic_keyword — из выдачи по синонимам.
Это боли `few_attributes` и `empty_keywords` в Диагнозе.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from i18n import t
from services.db import get_conn

# доля заполненных атрибутов
FILL_OK = 0.85     # от этого значения — зелёный
FILL_WARN = 0.5    # ниже — красный
MIN_BULLETS = 5    # Amazon даёт пять буллетов; меньше — недобор


@st.cache_data(ttl=300)
def load_attributes() -> pd.DataFrame:
    """Атрибуты и категория по всем ASIN×MP."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT asin, marketplace, product_type,
                   browse_node_id, browse_node_name, browse_path,
                   attrs_total, attrs_filled, attrs_empty,
                   has_generic_keyword, bullets_count, has_description
            FROM listing_attributes
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def attrs_map(df: pd.DataFrame | None = None) -> dict:
    """(asin, marketplace) -> словарь атрибутов."""
    df = load_attributes() if df is None else df
    if df.empty:
        return {}
    return {(r["asin"], r["marketplace"]): r.to_dict()
            for _, r in df.iterrows()}


def _num(v) -> float | None:
    """Число или None. pd.isna, а не `if v`: ноль заполненных атрибутов —
    валидное (и самое тревожное) значение, а NaN истинный."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _text(v) -> str:
    """Строка или пусто — без NaN, которые pandas отдаёт вместо NULL."""
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return str(v).strip()


def _flag(v) -> bool | None:
    """True / False / None (не знаем — данных нет)."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return bool(v)


def _totals(at: dict) -> tuple[float | None, float | None]:
    """(заполнено, всего). Всего восстанавливаем из filled + empty,
    если колонка attrs_total пустая."""
    filled = _num(at.get("attrs_filled"))
    total = _num(at.get("attrs_total"))
    if total is None:
        empty = _num(at.get("attrs_empty"))
        if filled is not None and empty is not None:
            total = filled + empty
    return filled, total


def node_short(at: dict | None) -> str:
    """Короткая подпись категории для чипа.

    Берём имя browse node, иначе последний сегмент пути. Путь режем с конца:
    «Bricolaje › Herramientas eléctricas › Sierras» — значимое в хвосте.
    """
    if not at:
        return "—"
    name = _text(at.get("browse_node_name"))
    if not name:
        path = _text(at.get("browse_path"))
        if path:
            name = [p.strip() for p in path.replace("/", "›").split("›")
                    if p.strip()][-1]
    if not name:
        return "—"
    return name if len(name) <= 22 else name[:21] + "…"


def fill_state(at: dict | None) -> tuple[str, str]:
    """Заполненность атрибутов: (состояние, подпись).

    Состояние — ok | warn | err | none, подпись — «12/27» для чипа.
    Числовая подпись без перевода: цифры одинаковы во всех языках.
    """
    if not at:
        return "none", "—"
    filled, total = _totals(at)
    if filled is None or not total:
        return "none", "—"
    label = f"{int(filled)}/{int(total)}"
    ratio = filled / total
    if ratio >= FILL_OK:
        return "ok", label
    if ratio >= FILL_WARN:
        return "warn", label
    return "err", label


def missing_critical(at: dict | None) -> list[str]:
    """Чего не хватает в первую очередь — переведённые подписи для чипа.

    Порядок по весу: без generic_keyword товар не находят по синонимам,
    без буллетов и описания нечего показать ни человеку, ни Rufus.
    """
    if not at:
        return []
    miss: list[str] = []

    if _flag(at.get("has_generic_keyword")) is False:
        miss.append(t("attr.crit.keywords"))

    bullets = _num(at.get("bullets_count"))
    if bullets is not None and bullets < MIN_BULLETS:
        miss.append(t("attr.crit.bullets"))

    if _flag(at.get("has_description")) is False:
        miss.append(t("attr.crit.description"))

    empty = _num(at.get("attrs_empty"))
    if empty:
        miss.append(f"{t('attr.crit.attributes')} {int(empty)}")

    return miss
