# -*- coding: utf-8 -*-
"""
pages/dashboard.py — Диагноз. Масштабируется до 100+ ASIN.

Шапка: сколько товаров требует внимания, деньги под риском, дельта
с прошлого прогона. Фильтры: severity, тип боли, маркетплейс, поиск.
Список: строка = товар (боли внутри), пагинация. Внизу — здоровые.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import TITLE_LIMIT, days_to_deadline
from i18n import t
from services.db import get_conn
from components.ui import (
    inject_fonts, verdict, limit_ruler_html, pain_card, eyebrow,
)

MIN_REVIEWS = 50
MIN_IMAGES = 7
GROUP_THRESHOLD = 1       # режим строк-групп всегда (единый вид на любом объёме)
PAGE_SIZE = 25
SEV_ORDER = {"red": 0, "amber": 1, "yellow": 2}
SEV_DOT = {"red": "🔴", "amber": "🟠", "yellow": "🟡"}
RULE_GROUP = {
    "title_over_limit": "тайтл",
    "out_of_stock": "сток",
    "low_reviews": "отзывы",
    "few_images": "медиа",
    "no_video": "медиа",
    "no_aplus": "контент",
}
MUTED = "#8A8578"

inject_fonts()


# ---------------------------------------------------------------- данные
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
                   s.asin, s.marketplace, s.title
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


@st.cache_data(ttl=300)
def load_scope() -> tuple[int, int]:
    """Сколько всего наших товаров в матрице (для «X из Y»)."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            "SELECT count(*) AS n FROM product_matrix WHERE is_competitor = FALSE",
            conn,
        )
        conn.close()
        return int(df.iloc[0]["n"]), 0
    except Exception:
        return 0, 0


@st.cache_data(ttl=300)
def load_delta() -> tuple[int, int]:
    """Новых / закрытых болей между последним и предыдущим прогоном."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            WITH runs AS (
                SELECT DISTINCT date_trunc('day', created_at) AS run_day
                FROM diagnosis ORDER BY run_day DESC LIMIT 2
            ),
            last_run AS (
                SELECT asin, marketplace, rule_id FROM diagnosis
                WHERE date_trunc('day', created_at) =
                      (SELECT max(run_day) FROM runs)
            ),
            prev_run AS (
                SELECT asin, marketplace, rule_id FROM diagnosis
                WHERE date_trunc('day', created_at) =
                      (SELECT min(run_day) FROM runs)
            )
            SELECT
                (SELECT count(*) FROM last_run l
                   WHERE NOT EXISTS (SELECT 1 FROM prev_run p
                     WHERE p.asin=l.asin AND p.marketplace=l.marketplace
                       AND p.rule_id=l.rule_id)) AS added,
                (SELECT count(*) FROM prev_run p
                   WHERE NOT EXISTS (SELECT 1 FROM last_run l
                     WHERE l.asin=p.asin AND l.marketplace=p.marketplace
                       AND l.rule_id=p.rule_id)) AS closed
            """,
            conn,
        )
        conn.close()
        return int(df.iloc[0]["added"] or 0), int(df.iloc[0]["closed"] or 0)
    except Exception:
        return 0, 0


def money_fmt(v) -> str:
    try:
        return f"€{float(v):,.0f}".replace(",", " ") + "/мес"
    except (TypeError, ValueError):
        return "не оценено"


# ---------------------------------------------------------------- карточки
def build_card_args(r: pd.Series, product_title: str | None) -> dict:
    rule = r.get("rule_id", "")
    money = money_fmt(r.get("money_impact"))
    digits = [int(s) for s in str(r["pain"]).split() if s.isdigit()]

    if rule == "title_over_limit":
        current = len(product_title) if product_title else (digits[0] if digits else TITLE_LIMIT)
        over = max(0, current - TITLE_LIMIT)
        return dict(
            kind_label="Тайтл",
            headline=f"Тайтл {current} симв. — Amazon перепишет сам",
            ruler_html=limit_ruler_html(current, TITLE_LIMIT,
                                        left_label=f"{TITLE_LIMIT} допуск",
                                        right_label=f"+{over} резать"),
            money=f"{current} / {TITLE_LIMIT} · превышение {over}",
        )
    if rule == "low_reviews":
        current = digits[0] if digits else 0
        return dict(
            kind_label="Отзывы",
            headline=f"{current} отзывов при пороге доверия {MIN_REVIEWS}+",
            ruler_html=limit_ruler_html(current, MIN_REVIEWS,
                                        left_label=f"{current} сейчас",
                                        right_label=f"цель {MIN_REVIEWS}",
                                        over_style=False),
            money=f"{current} / {MIN_REVIEWS}",
        )
    if rule == "few_images":
        current = digits[0] if digits else 0
        return dict(
            kind_label="Медиа",
            headline=f"Галерея: {current} фото при норме {MIN_IMAGES}+",
            ruler_html=limit_ruler_html(current, MIN_IMAGES,
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
    pain_card(
        severity=str(r["severity"]),
        asin=asin, marketplace=mp,
        product_title=product_title,
        cause=str(r["cause"]), action=str(r["action"]),
        **build_card_args(r, product_title),
    )


def chip_button(col, label: str, key: str, state_key: str, value: str,
                disabled: bool = False) -> None:
    active = st.session_state.get(state_key) == value
    if col.button(label, key=key, disabled=disabled,
                  type="primary" if active else "secondary"):
        st.session_state[state_key] = None if active else value
        st.session_state["diag_page"] = 1
        st.rerun()


# ---------------------------------------------------------------- страница
diag = load_diagnosis()
titles = load_titles()
title_map = {}
if not titles.empty:
    title_map = {(r["asin"], r["marketplace"]): r["title"]
                 for _, r in titles.iterrows()}

if diag.empty:
    st.header(t("nav.dashboard"))
    st.info(t("common.no_data"))
    st.stop()

total_products, _ = load_scope()
added, closed = load_delta()
affected = diag.groupby(["asin", "marketplace"]).ngroups
run_label = pd.to_datetime(diag["created_at"].max()).strftime("%d.%m %H:%M")

money_at_risk = pd.to_numeric(diag.get("money_impact"), errors="coerce").sum()
risk_html = (
    f"Под риском <span style='color:#E8590C;font-weight:700;'>€{money_at_risk:,.0f}</span>/мес"
    if money_at_risk else
    "Под риском <span style='color:#E8590C;font-weight:700;'>н/д</span> "
    "<span style='color:#8A8578;'>(заполни sku_economics)</span>"
)
delta_html = ""
if added or closed:
    delta_html = (
        f" · с прошлого прогона <span style='color:#E8590C;font-weight:600;'>"
        f"+{added} новых</span> · {closed} закрыто"
    )

headline = (f"{affected} товаров требуют внимания"
            + (f" из {total_products}" if total_products else ""))
verdict(headline, risk_html + delta_html, meta_right=f"прогон {run_label}")

st.download_button(t("dash.fix_all_csv"),
                   diag.to_csv(index=False).encode("utf-8-sig"),
                   file_name="diagnosis.csv", mime="text/csv")

# ---- фильтры: severity
s_counts = {s: int((diag["severity"] == s).sum()) for s in SEV_ORDER}
c1, c2, c3, c4 = st.columns([1, 1, 1, 3])
chip_button(c1, f"🔴 критично {s_counts['red']}", "f-red", "sev_filter", "red",
            s_counts["red"] == 0)
chip_button(c2, f"🟠 важно {s_counts['amber']}", "f-amber", "sev_filter", "amber",
            s_counts["amber"] == 0)
chip_button(c3, f"🟡 план {s_counts['yellow']}", "f-yellow", "sev_filter", "yellow",
            s_counts["yellow"] == 0)

# ---- фильтры: тип боли
diag = diag.copy()
diag["_group"] = diag["rule_id"].map(RULE_GROUP).fillna("другое")
groups_present = sorted(diag["_group"].unique())
gcols = st.columns(max(len(groups_present), 1) + 2)
for i, gname in enumerate(groups_present):
    n = int((diag["_group"] == gname).sum())
    chip_button(gcols[i], f"{gname} {n}", f"f-g-{gname}", "grp_filter", gname)

# ---- поиск и маркетплейсы
q_col, mp_col = st.columns([3, 2])
query = q_col.text_input("Поиск", label_visibility="collapsed",
                         placeholder="Поиск: ASIN, SKU или текст боли...")
mps = sorted(diag["marketplace"].unique())
mp_sel = mp_col.multiselect("MP", mps, default=[], label_visibility="collapsed",
                            placeholder="Все маркетплейсы")

view = diag
sev_f = st.session_state.get("sev_filter")
grp_f = st.session_state.get("grp_filter")
if sev_f:
    view = view[view["severity"] == sev_f]
if grp_f:
    view = view[view["_group"] == grp_f]
if mp_sel:
    view = view[view["marketplace"].isin(mp_sel)]
if query.strip():
    q = query.strip().lower()
    view = view[
        view["asin"].str.lower().str.contains(q, na=False)
        | view["sku_group"].astype(str).str.lower().str.contains(q, na=False)
        | view["pain"].astype(str).str.lower().str.contains(q, na=False)
    ]

if view.empty:
    st.caption("По этим фильтрам болей нет.")
    st.stop()

view = view.copy()
view["_o"] = view["severity"].map(SEV_ORDER).fillna(9)
n_products = view.groupby(["asin", "marketplace"]).ngroups

# ---------------------------------------------------------------- вывод
if n_products < GROUP_THRESHOLD:
    for _, r in view.sort_values(["_o", "created_at"],
                                 ascending=[True, False]).iterrows():
        render_pain(r, title_map)
else:
    groups = []
    for (asin, mp), g in view.groupby(["asin", "marketplace"]):
        groups.append({
            "asin": asin, "mp": mp, "rows": g,
            "worst": int(g["_o"].min()),
            "counts": {s: int((g["severity"] == s).sum()) for s in SEV_ORDER},
            "sku": g.iloc[0].get("sku_group") or asin,
            "money": pd.to_numeric(g.get("money_impact"), errors="coerce").sum(),
        })
    groups.sort(key=lambda x: (x["worst"], -(x["money"] or 0)))

    pages = max(1, (len(groups) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(st.session_state.get("diag_page", 1), pages)
    chunk = groups[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]

    st.caption(f"{len(groups)} товаров с болями · показано {len(chunk)}")

    for i, grp in enumerate(chunk):
        dots = " · ".join(
            f"{SEV_DOT[s]}{grp['counts'][s]}" for s in SEV_ORDER if grp["counts"][s]
        )
        ptitle = title_map.get((grp["asin"], grp["mp"])) or ""
        short = ptitle[:55] + ("…" if len(ptitle) > 55 else "")
        label = (f"{grp['sku']} · {grp['asin']} · {grp['mp']} · {dots}"
                 + (f" · {short}" if short else ""))
        with st.expander(label, expanded=(i == 0 and page == 1)):
            for _, r in grp["rows"].sort_values(
                    ["_o", "created_at"], ascending=[True, False]).iterrows():
                render_pain(r, title_map)

    if pages > 1:
        p1, p2, p3 = st.columns([1, 2, 1])
        if p1.button("← Назад", disabled=page <= 1):
            st.session_state["diag_page"] = page - 1
            st.rerun()
        p2.markdown(
            f"<div style='text-align:center;color:{MUTED};'>стр. {page} / {pages}</div>",
            unsafe_allow_html=True)
        if p3.button("Вперёд →", disabled=page >= pages):
            st.session_state["diag_page"] = page + 1
            st.rerun()

# ---- здоровые товары
if total_products:
    healthy = total_products - affected
    if healthy > 0:
        st.divider()
        st.markdown(
            f"<div style='color:{MUTED};font-size:13px;'>"
            f"{healthy} товаров без болей · "
            f"<span style='color:#2F6B3A;'>✓ здоровы</span></div>",
            unsafe_allow_html=True)
