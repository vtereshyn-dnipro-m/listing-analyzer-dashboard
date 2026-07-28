# -*- coding: utf-8 -*-
"""
pages/dashboard.py — Главная: Диагноз. Визуальный язык макета B+C.

При малом числе ASIN — плоский список карточек болей.
При GROUP_THRESHOLD+ товарах автоматически включается группировка:
строка-сводка на товар (боли свёрнуты), худший товар раскрыт.
Кликабельные чипы фильтруют список по severity.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import TITLE_LIMIT, days_to_deadline
from i18n import t
from services.db import get_conn
from components.ui import (
    inject_fonts, verdict, chips_row, limit_ruler_html, pain_card, eyebrow,
)

MIN_REVIEWS = 50
MIN_IMAGES = 7
GROUP_THRESHOLD = 6      # с этого числа товаров включаем группировку
SEV_ORDER = {"red": 0, "amber": 1, "yellow": 2}
SEV_DOT = {"red": "🔴", "amber": "🟠", "yellow": "🟡"}

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


def build_card_args(r: pd.Series, product_title: str | None) -> dict:
    """Собирает параметры карточки боли по rule_id."""
    rule = r.get("rule_id", "")
    money = money_fmt(r.get("money_impact"))

    if rule == "title_over_limit":
        current = len(product_title) if product_title else None
        if current is None:
            digits = [int(s) for s in str(r["pain"]).split() if s.isdigit()]
            current = digits[0] if digits else TITLE_LIMIT
        over = max(0, current - TITLE_LIMIT)
        return dict(
            kind_label="Тайтл",
            headline=f"Тайтл {current} симв. — Amazon перепишет сам",
            ruler_html=limit_ruler_html(
                current, TITLE_LIMIT,
                left_label=f"{TITLE_LIMIT} допуск",
                right_label=f"+{over} резать"),
            money=f"{current} / {TITLE_LIMIT} · превышение {over}",
        )
    if rule == "low_reviews":
        digits = [int(s) for s in str(r["pain"]).split() if s.isdigit()]
        current = digits[0] if digits else 0
        return dict(
            kind_label="Отзывы",
            headline=f"{current} отзывов при пороге доверия {MIN_REVIEWS}+",
            ruler_html=limit_ruler_html(
                current, MIN_REVIEWS,
                left_label=f"{current} сейчас",
                right_label=f"цель {MIN_REVIEWS}",
                over_style=False),
            money=f"{current} / {MIN_REVIEWS}",
        )
    if rule == "few_images":
        digits = [int(s) for s in str(r["pain"]).split() if s.isdigit()]
        current = digits[0] if digits else 0
        return dict(
            kind_label="Медиа",
            headline=f"Галерея: {current} фото при норме категории {MIN_IMAGES}+",
            ruler_html=limit_ruler_html(
                current, MIN_IMAGES,
                left_label=f"{current} фото",
                right_label=f"норма {MIN_IMAGES}+",
                over_style=False),
            money=f"{current} / {MIN_IMAGES}",
        )
    if rule == "no_video":
        return dict(kind_label="Медиа", headline="Нет видео на листинге",
                    ruler_html="", money="видео: нет")
    if rule == "no_aplus":
        return dict(kind_label="Контент", headline="Нет A+ контента",
                    ruler_html="", money="A+: нет")
    if rule == "out_of_stock":
        return dict(kind_label="Сток", headline="Товар недоступен к покупке",
                    ruler_html="", money=money)
    return dict(kind_label="Боль", headline=str(r["pain"]),
                ruler_html="", money=money)


def render_pain(r: pd.Series, title_map: dict) -> None:
    asin, mp = r["asin"], r["marketplace"]
    product_title = title_map.get((asin, mp))
    args = build_card_args(r, product_title)
    pain_card(
        severity=str(r["severity"]),
        asin=asin,
        marketplace=mp,
        product_title=product_title,
        cause=str(r["cause"]),
        action=str(r["action"]),
        **args,
    )


# ---------------------------------------------------------------- данные
diag = load_diagnosis()
titles = load_titles()

title_map: dict = {}
if not titles.empty:
    title_map = {
        (r["asin"], r["marketplace"]): r["title"] for _, r in titles.iterrows()
    }

if diag.empty:
    st.header(t("nav.dashboard"))
    st.info(t("common.no_data"))
    st.stop()

d = days_to_deadline()
run_label = ""
if "created_at" in diag.columns:
    run_label = pd.to_datetime(diag["created_at"].max()).strftime("%d.%m %H:%M")

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
    verdict(t("dash.header", n=n_over, days=d),
            f"Лимит {TITLE_LIMIT} симв. · Под риском: {risk_html}",
            meta_right=f"прогон {run_label}")
else:
    verdict(t("nav.dashboard"),
            f"Все тайтлы в пределах {TITLE_LIMIT} символов",
            meta_right=f"прогон {run_label}")

csv = diag.to_csv(index=False).encode("utf-8-sig")
st.download_button(t("dash.fix_all_csv"), csv,
                   file_name="diagnosis.csv", mime="text/csv")

# ---------------------------------------------------------------- фильтр
s_red = int((diag["severity"] == "red").sum())
s_amber = int((diag["severity"] == "amber").sum())
s_yellow = int((diag["severity"] == "yellow").sum())
mp_list = " · ".join(sorted(diag["marketplace"].unique()))

f1, f2, f3, f4 = st.columns([1, 1, 1, 3])
sev_filter = st.session_state.get("sev_filter")
if f1.button(f"🔴 критично {s_red}", disabled=s_red == 0,
             type="primary" if sev_filter == "red" else "secondary"):
    st.session_state["sev_filter"] = None if sev_filter == "red" else "red"
    st.rerun()
if f2.button(f"🟠 важно {s_amber}", disabled=s_amber == 0,
             type="primary" if sev_filter == "amber" else "secondary"):
    st.session_state["sev_filter"] = None if sev_filter == "amber" else "amber"
    st.rerun()
if f3.button(f"🟡 план {s_yellow}", disabled=s_yellow == 0,
             type="primary" if sev_filter == "yellow" else "secondary"):
    st.session_state["sev_filter"] = None if sev_filter == "yellow" else "yellow"
    st.rerun()
f4.markdown(
    f"<div style='padding-top:8px;color:#8A8578;font-size:13px;'>"
    f"{mp_list} · {diag['asin'].nunique()} ASIN"
    + (" · фильтр активен" if sev_filter else "") + "</div>",
    unsafe_allow_html=True,
)

view = diag if not sev_filter else diag[diag["severity"] == sev_filter]
if view.empty:
    st.caption("По этому фильтру болей нет.")
    st.stop()

view = view.copy()
view["_o"] = view["severity"].map(SEV_ORDER).fillna(9)

# ---------------------------------------------------------------- вывод
n_products = view.groupby(["asin", "marketplace"]).ngroups

if n_products < GROUP_THRESHOLD:
    # плоский список — как раньше
    for _, r in view.sort_values(["_o", "created_at"],
                                 ascending=[True, False]).head(50).iterrows():
        render_pain(r, title_map)
else:
    # группировка по товару: строка-сводка + раскрытие
    groups = []
    for (asin, mp), g in view.groupby(["asin", "marketplace"]):
        groups.append({
            "asin": asin, "mp": mp, "rows": g,
            "worst": int(g["_o"].min()),
            "red": int((g["severity"] == "red").sum()),
            "amber": int((g["severity"] == "amber").sum()),
            "yellow": int((g["severity"] == "yellow").sum()),
            "sku": g.iloc[0].get("sku_group") or asin,
            "money": pd.to_numeric(g.get("money_impact"), errors="coerce").sum(),
        })
    groups.sort(key=lambda x: (x["worst"], -(x["money"] or 0)))

    st.caption(f"{len(groups)} товаров с болями · развернут самый проблемный")

    for i, grp in enumerate(groups):
        dots = " ".join(filter(None, [
            f"{SEV_DOT['red']}{grp['red']}" if grp["red"] else "",
            f"{SEV_DOT['amber']}{grp['amber']}" if grp["amber"] else "",
            f"{SEV_DOT['yellow']}{grp['yellow']}" if grp["yellow"] else "",
        ]))
        product_title = title_map.get((grp["asin"], grp["mp"])) or ""
        short = product_title[:60] + ("…" if len(product_title) > 60 else "")
        label = (f"{grp['sku']} · {grp['asin']} · {grp['mp']} · {dots}"
                 + (f" · «{short}»" if short else ""))
        with st.expander(label, expanded=(i == 0)):
            for _, r in grp["rows"].sort_values(
                    ["_o", "created_at"], ascending=[True, False]).iterrows():
                render_pain(r, title_map)

if len(view) > 50 and n_products < GROUP_THRESHOLD:
    st.caption(f"Показаны первые 50 из {len(view)} — полный список в CSV")
