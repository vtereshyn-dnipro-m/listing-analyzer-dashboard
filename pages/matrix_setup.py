# -*- coding: utf-8 -*-
"""
pages/matrix_setup.py — Настройка: Матрица товаров.

Единственная страница с записью в БД (product_matrix) — разрешённые
INSERT/UPDATE, никакого DDL. Ввод пачкой в любом формате:
    GS-98, B0DKFVFT29, es
    GS-98, B0XXXXXXXX, es, конкурент
    B0YYYYYYYY
    https://www.amazon.es/dp/B0ZZZZZZZZ
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from i18n import t
from services.db import get_conn, add_matrix_rows, parse_asin_lines

st.header(t("nav.matrix"))

st.markdown(
    "Формат — построчно, любой из вариантов вперемешку:  \n"
    "`SKU, ASIN, маркетплейс[, конкурент]` · голый `ASIN` · ссылка amazon"
)

text = st.text_area(
    "ASIN пачкой",
    height=180,
    placeholder="GS-98, B0DKFVFT29, es\nGS-98, B0XXXXXXXX, es, конкурент\nB0YYYYYYYY",
    label_visibility="collapsed",
)

if st.button("Добавить в матрицу", type="primary", disabled=not text.strip()):
    rows = parse_asin_lines(text)
    if not rows:
        st.warning("Не нашёл ни одного ASIN — проверь формат")
    else:
        try:
            conn = get_conn()
            n = add_matrix_rows(conn, rows)
            conn.close()
            st.success(f"Добавлено/обновлено: {n}")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"БД недоступна: {e}")

st.divider()

# ---- текущая матрица
try:
    conn = get_conn()
    df = pd.read_sql(
        "SELECT sku_group, asin, marketplace, is_competitor, added_at "
        "FROM product_matrix ORDER BY sku_group, is_competitor, marketplace, asin",
        conn,
    )
    conn.close()
except Exception:
    df = pd.DataFrame()

if df.empty:
    st.caption(t("common.no_data"))
else:
    df["кто"] = df["is_competitor"].map(
        {True: t("common.competitor"), False: t("common.our")}
    )
    st.dataframe(
        df[["sku_group", "asin", "marketplace", "кто", "added_at"]],
        use_container_width=True,
        hide_index=True,
    )
    ours = int((~df.is_competitor).sum())
    comps = int(df.is_competitor.sum())
    st.caption(f"Всего: {len(df)} · наших {ours} · конкурентов {comps}")
