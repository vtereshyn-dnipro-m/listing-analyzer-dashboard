# -*- coding: utf-8 -*-
"""
pages/dashboard.py — Главная: Диагноз.

Читает diagnosis (последняя запись на каждую пару asin+rule) — никакой
логики и никакого DDL здесь нет. Кэш st.cache_data, как в Кабинете.
Нет данных -> честные пустые состояния.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import TITLE_LIMIT, days_to_deadline
from i18n import t
from services.db import get_conn

SEV_ICON = {"red": "🔴", "amber": "🟠", "yellow": "🟡"}
SEV_ORDER = {"red": 0, "amber": 1, "yellow": 2}


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
def load_analysis() -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (a.asin, a.marketplace)
                   a.asin, a.marketplace, a.title_len, a.title_over
            FROM listing_analysis a
            ORDER BY a.asin, a.marketplace, a.analyzed_at DESC
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def money_fmt(v) -> str:
    try:
        return f"€{float(v):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


diag = load_diagnosis()
ana = load_analysis()

d = days_to_deadline()
run_label = ""
if not diag.empty and "created_at" in diag.columns:
    run_label = pd.to_datetime(diag["created_at"].max()).strftime("%d.%m %H:%M")

st.caption(f"{t('nav.dashboard').lower()} · {run_label or '—'}")

n_over = int((ana["title_over"] > 0).sum()) if not ana.empty else 0
money_at_risk = None
if not diag.empty and "money_impact" in diag.columns:
    m = diag.loc[diag["rule_id"] == "title_over_limit", "money_impact"].dropna()
    money_at_risk = float(m.sum()) if len(m) else None

if n_over > 0:
    st.header(t("dash.header", n=n_over, days=d))
    risk_txt = money_fmt(money_at_risk) if money_at_risk else "н/д (заполни sku_economics)"
    st.markdown(t("dash.reason", money=risk_txt))
elif ana.empty:
    st.header(t("nav.dashboard"))
    st.info(t("common.no_data"))
else:
    st.header(t("nav.dashboard"))
    st.success(f"Все тайтлы в пределах {TITLE_LIMIT} символов")

if not diag.empty:
    c1, c2, _ = st.columns([1, 1, 2])
    with c1:
        csv = diag.to_csv(index=False).encode("utf-8-sig")
        st.download_button(t("dash.fix_all_csv"), csv,
                           file_name="diagnosis.csv", mime="text/csv",
                           type="primary")
    with c2:
        top10_only = st.toggle(t("dash.top10"), value=False)
else:
    top10_only = False

st.divider()

if diag.empty:
    st.caption(t("dash.no_diagnosis"))
    st.stop()

diag["_sev_order"] = diag["severity"].map(SEV_ORDER).fillna(9)
view = diag.sort_values(["_sev_order", "created_at"], ascending=[True, False])

if top10_only and "money_impact" in view.columns:
    top_asins = (view.groupby("asin")["money_impact"].sum()
                 .sort_values(ascending=False).head(10).index)
    view = view[view["asin"].isin(top_asins)]

s_red = int((view["severity"] == "red").sum())
s_amber = int((view["severity"] == "amber").sum())
s_yellow = int((view["severity"] == "yellow").sum())
m1, m2, m3, m4 = st.columns(4)
m1.metric("🔴 критично", s_red)
m2.metric("🟠 важно", s_amber)
m3.metric("🟡 план", s_yellow)
m4.metric("ASIN с болями", view["asin"].nunique())

for _, r in view.head(50).iterrows():
    sev = SEV_ICON.get(str(r["severity"]), "·")
    fix = t("pain.fix_now") if r.get("fix_mode") == "fix_now" else t("pain.test")
    money = (money_fmt(r["money_impact"]) + "/мес"
             if pd.notna(r.get("money_impact")) else "не оценено")
    with st.container(border=True):
        st.markdown(
            f"{sev} **{r['pain']}**  \n"
            f"`{r['asin']}` · {r['marketplace']}"
            + (f" · {r['sku_group']}" if r.get("sku_group") else "")
        )
        st.markdown(
            f"Причина: {r['cause']}  \n"
            f"Действие: **{r['action']}**  \n"
            f"Цена бездействия: **{money}** · {fix}"
        )

if len(view) > 50:
    st.caption(f"Показаны первые 50 из {len(view)} — полный список в CSV")
