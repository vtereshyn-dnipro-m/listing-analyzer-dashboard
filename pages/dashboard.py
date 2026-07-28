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
                   s.asin, s.marketplace, s.title,
                   s.raw->>'main_image' AS main_image
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
        image_url=image_map.get((asin, mp)),
        cause=str(r["cause"]), action=str(r["action"]),
        **build_card_args(r, product_title),
    )


# ---------------------------------------------------------------- страница
diag = load_diagnosis()
titles = load_titles()
title_map, image_map = {}, {}
if not titles.empty:
    title_map = {(r["asin"], r["marketplace"]): r["title"]
                 for _, r in titles.iterrows()}
    image_map = {(r["asin"], r["marketplace"]): r.get("main_image")
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

# ---- фильтры: severity и тип боли (компактные сегменты)
diag = diag.copy()
diag["_group"] = diag["rule_id"].map(RULE_GROUP).fillna("другое")

s_counts = {s: int((diag["severity"] == s).sum()) for s in SEV_ORDER}
sev_opts = [s for s in ("red", "amber", "yellow") if s_counts[s]]
sev_labels = {"red": "критично", "amber": "важно", "yellow": "план"}
grp_opts = sorted(diag["_group"].unique())
grp_counts = {g: int((diag["_group"] == g).sum()) for g in grp_opts}


def _seg(col, options, fmt, key):
    """Сегмент-контрол с фолбэком на multiselect для старых версий."""
    try:
        return col.segmented_control(
            key, options, format_func=fmt, default=None,
            selection_mode="single", label_visibility="collapsed", key=key)
    except AttributeError:
        sel = col.multiselect(key, options, default=[], format_func=fmt,
                              label_visibility="collapsed", key=key)
        return sel[0] if sel else None


fc1, fc2 = st.columns([1.1, 1.6])
sev_f = _seg(fc1, sev_opts,
             lambda s: f"{SEV_DOT[s]} {sev_labels[s]} {s_counts[s]}", "sev_seg")
grp_f = _seg(fc2, grp_opts,
             lambda g: f"{g} {grp_counts[g]}", "grp_seg")

# ---- поиск, маркетплейсы, вид
q_col, mp_col, mode_col = st.columns([3, 2, 1.6])
query = q_col.text_input("Поиск", label_visibility="collapsed",
                         placeholder="Поиск: ASIN, SKU или текст боли...")
mps = sorted(diag["marketplace"].unique())
mp_sel = mp_col.multiselect("MP", mps, default=[], label_visibility="collapsed",
                            placeholder="Все маркетплейсы")
try:
    mode = mode_col.segmented_control(
        "Вид", ["Карточки", "Таблица"], default="Карточки",
        selection_mode="single", label_visibility="collapsed", key="diag_mode")
except AttributeError:
    mode = mode_col.radio("Вид", ["Карточки", "Таблица"], horizontal=True,
                          label_visibility="collapsed", key="diag_mode")
mode = mode or "Карточки"

view = diag
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
if mode == "Таблица":
    tbl = view.copy()
    # боли одного товара идут подряд; товары — по худшей боли, потом по числу болей
    prod = tbl.groupby(["asin", "marketplace"]).agg(
        _worst=("_o", "min"), _cnt=("_o", "size")).reset_index()
    tbl = tbl.merge(prod, on=["asin", "marketplace"], how="left")
    tbl = tbl.sort_values(["_worst", "_cnt", "asin", "_o"],
                          ascending=[True, False, True, True])

    tbl["товар"] = tbl.apply(
        lambda r: (r["sku_group"] if r["sku_group"] and r["sku_group"] != r["asin"]
                   else r["asin"]), axis=1)
    tbl["название"] = tbl.apply(
        lambda r: (title_map.get((r["asin"], r["marketplace"])) or "")[:60], axis=1)
    tbl["важность"] = tbl["severity"].map(
        {"red": "🔴 критично", "amber": "🟠 важно", "yellow": "🟡 план"})
    tbl["болей"] = tbl["_cnt"]
    tbl["ссылка"] = tbl.apply(
        lambda r: f"https://www.amazon.{r['marketplace']}/dp/{r['asin']}", axis=1)

    st.dataframe(
        tbl[["товар", "asin", "marketplace", "название", "болей",
             "важность", "_group", "pain", "action", "ссылка"]],
        column_config={
            "товар": st.column_config.TextColumn("Товар", width="small"),
            "asin": st.column_config.TextColumn("ASIN", width="small"),
            "marketplace": st.column_config.TextColumn("MP", width="small"),
            "название": st.column_config.TextColumn("Название", width="medium"),
            "болей": st.column_config.NumberColumn("Болей", width="small"),
            "важность": st.column_config.TextColumn("Важность", width="small"),
            "_group": st.column_config.TextColumn("Тип", width="small"),
            "pain": st.column_config.TextColumn("Боль", width="large"),
            "action": st.column_config.TextColumn("Действие", width="medium"),
            "ссылка": st.column_config.LinkColumn("Листинг", display_text="открыть"),
        },
        hide_index=True, use_container_width=True, height=560,
    )
    st.caption(
        f"{len(tbl)} болей по {prod.shape[0]} товарам · "
        "строки одного товара идут подряд · сортировка колонок — клик по заголовку"
    )
elif n_products < GROUP_THRESHOLD:
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
        head = (f"{grp['sku']} · {grp['asin']}"
                if grp["sku"] and grp["sku"] != grp["asin"] else grp["asin"])
        label = (f"{head} · {grp['mp']} · {dots}"
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
