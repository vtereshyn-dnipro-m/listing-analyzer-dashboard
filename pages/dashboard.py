# -*- coding: utf-8 -*-
"""
pages/dashboard.py — Шаг 6. Главная: Диагноз.

Читает ТОЛЬКО готовые view (diagnosis_latest, analysis_latest) — никакой
логики и никакого DDL здесь нет (правило: миграции делает пайплайн).
Кэш st.cache_data, как в Кабинете. Нет данных -> честные пустые состояния.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import TITLE_LIMIT, HIGHLIGHTS_LIMIT, days_to_deadline
from i18n import t
from services.db import get_conn

SEV_ICON = {3: "🔴", 2: "🟠", 1: "🟡"}


@st.cache_data(ttl=300)
def load_diagnosis() -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql("SELECT * FROM diagnosis_latest", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_analysis() -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            "SELECT asin, marketplace, sku_group, title_len, split_required "
            "FROM analysis_latest WHERE is_competitor = FALSE", conn)
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
if not diag.empty and "run_at" in diag.columns:
    run_label = pd.to_datetime(diag["run_at"].iloc[0]).strftime("%d.%m %H:%M")

st.caption(f"{t('nav.dashboard').lower()} · {run_label or '—'}")

n_over = int(ana["split_required"].sum()) if not ana.empty else 0
money_at_risk = None
if not diag.empty:
    m = diag.loc[diag["pain_code"] == "TITLE_OVER_75", "money_eur"].dropna()
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

view = diag.sort_values("priority", ascending=False)
if top10_only:
    top_asins = (view.groupby("asin")["money_eur"].sum()
                 .sort_values(ascending=False).head(10).index)
    view = view[view["asin"].isin(top_asins)]

s3 = int((view["severity"] == 3).sum())
s2 = int((view["severity"] == 2).sum())
s1 = int((view["severity"] == 1).sum())
m1, m2, m3, m4 = st.columns(4)
m1.metric("🔴 критично", s3)
m2.metric("🟠 важно", s2)
m3.metric("🟡 план", s1)
m4.metric("ASIN с болями", view["asin"].nunique())

for _, r in view.head(50).iterrows():
    sev = SEV_ICON.get(int(r["severity"]), "·")
    fix = t("pain.fix_now") if r["fix_type"] == "fix_now" else t("pain.test")
    money = money_fmt(r["money_eur"]) + "/мес" if pd.notna(r.get("money_eur")) \
        else f"~{r['money_pct']:.0f}% revenue"
    with st.container(border=True):
        st.markdown(
            f"{sev} **{r['pain_ru']}**  \n"
            f"`{r['asin']}` · {r['marketplace']}"
            + (f" · {r['sku_group']}" if r.get("sku_group") else "")
        )
        st.markdown(
            f"Причина: {r['cause_ru']}  \n"
            f"Действие: **{r['action_ru']}**  \n"
            f"Цена бездействия: **{money}** · {fix}"
        )
        with st.expander("обоснование цифры"):
            st.caption(r["money_basis"])

if len(view) > 50:
    st.caption(f"Показаны первые 50 из {len(view)} — полный список в CSV")
