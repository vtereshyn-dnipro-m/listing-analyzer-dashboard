# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import TITLE_LIMIT, days_to_deadline
from i18n import t
from services.db import get_conn
from components.ui import (
    inject_fonts, verdict, chips_row, limit_ruler_html, pain_card,
)

MIN_REVIEWS = 50

inject_fonts()


@st.cache_data(ttl=300)
def load_diagnosis() -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (d.asin, d.marketplace, d.rule_id) d.*
            FROM diagnosis d
            ORDER BY d.asin, d.marketplace, d.rule_id, d.created_at DESC
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_titles() -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (s.asin, s.marketplace)
                   s.asin, s.marketplace, s.title, s.review_count
            FROM listing_snapshots s
            WHERE s.ok = TRUE AND s.title <> ''
            ORDER BY s.asin, s.marketplace, s.fetched_at DESC
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def money_fmt(v) -> str:
    try:
        return f"€{float(v):,.0f}".replace(",", " ") + "/мес"
    except (TypeError, ValueError):
        return "не оценено"


diag = load_diagnosis()
titles = load_titles()

title_map: dict = {}
if not titles.empty:
    title_map = {
        (r["asin"], r["marketplace"]): r["title"] for _, r in titles.iterrows()
    }

d = days_to_deadline()
run_label = ""
if not diag.empty and "created_at" in diag.columns:
    run_label = pd.to_datetime(diag["created_at"].max()).strftime("%d.%m %H:%M")

if diag.empty:
    st.header(t("nav.dashboard"))
    st.info(t("common.no_data"))
    st.stop()

n_over = int((diag["rule_id"] == "title_over_limit").sum())
money_at_risk = diag.loc[
    diag["rule_id"] == "title_over_limit", "money_impact"
].dropna().sum()
risk_html = (
    f"<span style='color:#E8590C;font-weight:700;'>€{money_at_risk:,.0f}</span>/мес revenue"
    if money_at_risk
    else "<span style='color:#E8590C;font-weight:700;'>н/д</span> "
         "<span style='color:#8A8578;'>(заполни sku_economics)</span>"
)

if n_over > 0:
    verdict(
        t("dash.header", n=n_over, days=d),
        f"Лимит {TITLE_LIMIT} симв. с 27.07 · Под риском: {risk_html}",
        meta_right=f"прогон {run_label}",
    )
else:
    verdict(
        t("nav.dashboard"),
        f"Все тайтлы в пределах {TITLE_LIMIT} символов",
        meta_right=f"прогон {run_label}",
    )

csv = diag.to_csv(index=False).encode("utf-8-sig")
st.download_button(t("dash.fix_all_csv"), csv,
                   file_name="diagnosis.csv", mime="text/csv")

s_red = int((diag["severity"] == "red").sum())
s_amber = int((diag["severity"] == "amber").sum())
s_yellow = int((diag["severity"] == "yellow").sum())
mp_list = " · ".join(sorted(diag["marketplace"].unique()))
chips_row(s_red, s_amber, s_yellow,
          extra=f"{mp_list} · {diag['asin'].nunique()} ASIN")

SEV_ORDER = {"red": 0, "amber": 1, "yellow": 2}
diag["_o"] = diag["severity"].map(SEV_ORDER).fillna(9)
view = diag.sort_values(["_o", "created_at"], ascending=[True, False])

for _, r in view.head(50).iterrows():
    asin, mp = r["asin"], r["marketplace"]
    product_title = title_map.get((asin, mp))
    money = money_fmt(r.get("money_impact"))
    rule = r.get("rule_id", "")

    if rule == "title_over_limit":
        current = len(product_title) if product_title else None
        if current is None:
            digits = [int(s) for s in str(r["pain"]).split() if s.isdigit()]
            current = digits[0] if digits else TITLE_LIMIT
        over = max(0, current - TITLE_LIMIT)
        ruler = limit_ruler_html(
            current, TITLE_LIMIT,
            left_label=f"{TITLE_LIMIT} допуск",
            right_label=f"+{over} резать",
        )
        headline = f"Тайтл {current} симв. — Amazon перепишет сам"
        kind = "Тайтл"
        money_line = f"{current} / {TITLE_LIMIT} · превышение {over}"
    elif rule == "low_reviews":
        digits = [int(s) for s in str(r["pain"]).split() if s.isdigit()]
        current = digits[0] if digits else 0
        ruler = limit_ruler_html(
            current, MIN_REVIEWS,
            left_label=f"{current} сейчас",
            right_label=f"цель {MIN_REVIEWS}",
            over_style=False,
        )
        headline = f"{current} отзывов при пороге доверия {MIN_REVIEWS}+"
        kind = "Отзывы"
        money_line = f"{current} / {MIN_REVIEWS}"
    elif rule == "out_of_stock":
        ruler = ""
        headline = "Товар недоступен к покупке"
        kind = "Сток"
        money_line = money
    else:
        ruler = ""
        headline = str(r["pain"])
        kind = "Боль"
        money_line = money

    pain_card(
        severity=str(r["severity"]),
        kind_label=kind,
        asin=asin,
        marketplace=mp,
        headline=headline,
        product_title=product_title,
        ruler_html=ruler,
        cause=str(r["cause"]),
        action=str(r["action"]),
        money=money_line,
    )

if len(view) > 50:
    st.caption(f"Показаны первые 50 из {len(view)} — полный список в CSV")
