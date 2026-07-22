# -*- coding: utf-8 -*-
"""
pages/dashboard.py — Диагноз. Первый экран = вердикт, не форма.
Только чтение из diagnosis (последний прогон по каждому sku_group).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from i18n import t
from services.db import get_conn

st.header(t("nav.diagnosis"))

SEVERITY_ORDER = {"red": 0, "amber": 1, "yellow": 2}
SEVERITY_ICON = {"red": "🔴", "amber": "🟠", "yellow": "🟡"}

try:
    conn = get_conn()
    df = pd.read_sql(
        """
        SELECT d.*
        FROM diagnosis d
        INNER JOIN (
            SELECT sku_group, MAX(created_at) AS max_created
            FROM diagnosis GROUP BY sku_group
        ) latest
            ON d.sku_group = latest.sku_group
           AND d.created_at >= latest.max_created - INTERVAL '5 minutes'
        ORDER BY d.created_at DESC
        """,
        conn,
    )
    conn.close()
except Exception as e:
    st.error(f"БД недоступна: {e}")
    st.stop()

if df.empty:
    st.markdown("### Болей не найдено")
    st.caption(
        "Либо каталог здоров, либо данные ещё не собраны — "
        "прогони пайплайн на странице «Матрица товаров»."
    )
    st.stop()

df["_order"] = df["severity"].map(SEVERITY_ORDER).fillna(9)
df = df.sort_values(["_order", "created_at"], ascending=[True, False])

red_count = int((df["severity"] == "red").sum())
st.markdown(
    f"**{len(df)} болей найдено** · критичных: {red_count}"
)

for _, p in df.iterrows():
    icon = SEVERITY_ICON.get(p["severity"], "•")
    with st.container(border=True):
        st.markdown(f"{icon} **{p['asin']}** ({p['marketplace']}) · {p['pain']}")
        st.caption(f"Причина: {p['cause']}")
        money = p.get("money_impact")
        if money and not pd.isna(money):
            st.markdown(f":red[**${money:,.0f}/мес под риском**]")
        st.markdown(f"→ **{p['action']}**")
