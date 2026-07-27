# -*- coding: utf-8 -*-
"""
pages/catalog.py — Каталог: все тайтлы против лимитов 75/125.

Одна карточка на товар: тайтл, линейка-допуск title, линейка highlights,
статусы. Сортировка: сначала превышения (по величине), потом здоровые.
Только чтение: listing_analysis (последний анализ) + listing_snapshots
(живой тайтл) + product_matrix (sku/кто).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import TITLE_LIMIT, HIGHLIGHTS_LIMIT
from i18n import t
from services.db import get_conn
from components.ui import inject_fonts, eyebrow, limit_ruler_html

inject_fonts()

INK = "#1A1815"
MUTED = "#8A8578"
BORDER = "#E7E4DD"
CARD = "#FFFFFF"
ACCENT = "#E8590C"
OK_TEXT = "#2F6B3A"
MONO = '"JetBrains Mono","SFMono-Regular",Consolas,monospace'

st.header(t("nav.catalog"))


@st.cache_data(ttl=300)
def load_catalog() -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (a.asin, a.marketplace)
                   a.asin, a.marketplace, a.title_len, a.title_over,
                   a.highlights_len, a.analyzed_at,
                   s.title, s.in_stock, s.review_count,
                   m.sku_group, m.is_competitor
            FROM listing_analysis a
            LEFT JOIN LATERAL (
                SELECT title, in_stock, review_count
                FROM listing_snapshots s
                WHERE s.asin = a.asin AND s.marketplace = a.marketplace
                  AND s.ok = TRUE AND s.title <> ''
                ORDER BY s.fetched_at DESC LIMIT 1
            ) s ON TRUE
            LEFT JOIN product_matrix m
                ON m.asin = a.asin AND m.marketplace = a.marketplace
            ORDER BY a.asin, a.marketplace, a.analyzed_at DESC
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


df = load_catalog()

if df.empty:
    st.caption(t("common.no_data"))
    st.stop()

# только строки с реальным тайтлом (битые прогоны не показываем)
df = df[df["title"].notna() & (df["title"] != "")].copy()
if df.empty:
    st.caption(t("common.no_data"))
    st.stop()

df["title_len_actual"] = df["title"].str.len()
df["over_actual"] = (df["title_len_actual"] - TITLE_LIMIT).clip(lower=0)

n_over = int((df["over_actual"] > 0).sum())
total = len(df)

# ---- сводка
if n_over > 0:
    summary = (
        f"<span style='color:{ACCENT};font-weight:700;'>{n_over}</span>"
        f" из {total} тайтлов превышают лимит {TITLE_LIMIT} симв."
    )
else:
    summary = (
        f"<span style='color:{OK_TEXT};font-weight:700;'>Все {total}</span>"
        f" тайтлов в пределах {TITLE_LIMIT} симв."
    )
st.markdown(
    f"<div style='font-size:15px;color:{INK};margin-bottom:16px;'>{summary}</div>",
    unsafe_allow_html=True,
)

# ---- сортировка: превышения первыми, по величине
df = df.sort_values(["over_actual", "title_len_actual"], ascending=[False, False])

for _, r in df.iterrows():
    asin, mp = r["asin"], r["marketplace"]
    tl = int(r["title_len_actual"])
    over = int(r["over_actual"])
    hl = int(r["highlights_len"] or 0)
    hl_over = max(0, hl - HIGHLIGHTS_LIMIT)

    who = t("common.competitor") if r["is_competitor"] else t("common.our")
    sku = r["sku_group"] or asin
    edge = ACCENT if over > 0 else OK_TEXT

    title_ruler = limit_ruler_html(
        tl, TITLE_LIMIT,
        left_label=f"{TITLE_LIMIT}",
        right_label=(f"+{over} резать" if over > 0 else f"свободно {TITLE_LIMIT - tl}"),
    )

    status_right = (
        f"<span style='font-family:{MONO};font-size:13px;font-weight:700;color:{ACCENT};'>"
        f"{tl} / {TITLE_LIMIT} · +{over}</span>"
        if over > 0 else
        f"<span style='font-family:{MONO};font-size:13px;font-weight:600;color:{OK_TEXT};'>"
        f"{tl} / {TITLE_LIMIT} ✓</span>"
    )

    short = r["title"][:150] + ("…" if len(r["title"]) > 150 else "")

    st.markdown(
        f"""
        <div style="background:{CARD};border:1px solid {BORDER};
                    border-left:3px solid {edge};border-radius:0 12px 12px 0;
                    padding:16px 20px;margin-bottom:12px;">
          <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;">
            {eyebrow(f"{sku} · <a href='https://www.amazon.{mp}/dp/{asin}' target='_blank' style='color:{MUTED};text-decoration:underline;'>{asin}</a> · {mp} · {who}")}
            {status_right}
          </div>
          <div style="font-size:13px;color:{MUTED};margin-bottom:6px;">«{short}»</div>
          {title_ruler}
          <div style="font-size:12px;color:{MUTED};">
            highlights: <span style="font-family:{MONO};">{hl} / {HIGHLIGHTS_LIMIT}</span>
            {f"· <span style='color:{ACCENT};'>+{hl_over}</span>" if hl_over > 0 else "· ✓"}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
