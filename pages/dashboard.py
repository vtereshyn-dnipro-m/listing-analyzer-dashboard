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

from config import TITLE_LIMIT as _TL_DEFAULT, days_to_deadline
from i18n import t
from services.db import get_conn
from services.settings import get_int
from services.economics import (
    econ_map, money_at_risk, fmt_money, fmt_conversion,
)
from components.ui import (
    inject_fonts, verdict, limit_ruler_html, pain_card, eyebrow,
)

TITLE_LIMIT = get_int("limit.title", _TL_DEFAULT)
MIN_REVIEWS = get_int("threshold.min_reviews", 50)
MIN_IMAGES = get_int("threshold.min_images", 7)
GROUP_THRESHOLD = 1       # режим строк-групп всегда (единый вид на любом объёме)
PAGE_SIZE = 25
SEV_ORDER = {"red": 0, "amber": 1, "yellow": 2}
SEV_DOT = {"red": "🔴", "amber": "🟠", "yellow": "🟡"}
# группа правила — технический код, подпись берётся из i18n (group.*)
RULE_GROUP = {
    "title_over_limit": "title",
    "out_of_stock": "stock",
    "low_reviews": "reviews",
    "few_images": "media",
    "no_video": "media",
    "no_aplus": "content",
    "low_ctr": "search",
    "no_shipping_template": "shipping",
    "empty_keywords": "attributes",
    "few_attributes": "attributes",
    "hard_to_scan": "title",
}
MUTED = "#8A8578"

inject_fonts()
st.title(t("nav.dashboard"))


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
                   s.asin, s.marketplace, s.title, s.fetched_at,
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
        return f"€{float(v):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return t("common.not_estimated")


# ---------------------------------------------------------------- карточки

def cause_text(r: pd.Series) -> str:
    """Причина боли: из i18n по rule_id, иначе текст из базы.

    Правила пишут русский текст при создании боли — для перевода берём
    его по идентификатору правила, а старые записи показываем как есть.
    """
    rule = r.get("rule_id", "")
    key = f"cause.{rule}"
    val = t(key)
    return val if val != key else str(r.get("cause") or "")


def action_text(r: pd.Series) -> str:
    rule = r.get("rule_id", "")
    key = f"action.{rule}"
    val = t(key)
    return val if val != key else str(r.get("action") or "")


def build_card_args(r: pd.Series, product_title: str | None) -> dict:
    rule = r.get("rule_id", "")
    money = money_fmt(r.get("money_impact"))
    _e = ECON.get((r["asin"], r["marketplace"]))
    _risk = money_at_risk(rule, _e.get("revenue_30d")) if _e else 0.0
    risk_txt = fmt_money(_risk) if _risk else ""
    digits = [int(s) for s in str(r["pain"]).split() if s.isdigit()]

    if rule == "title_over_limit":
        current = len(product_title) if product_title else (digits[0] if digits else TITLE_LIMIT)
        over = max(0, current - TITLE_LIMIT)
        return dict(
            kind_label=t("card.title"),
            headline=t("pain.title_over", n=current),
            ruler_html=limit_ruler_html(
                current, TITLE_LIMIT,
                left_label=f"{TITLE_LIMIT} {t('ruler.limit')}",
                right_label=f"+{over} {t('ruler.cut')}"),
            money=(f"{current} / {TITLE_LIMIT} · {t('ruler.excess')} {over}"
                   + (f" · {risk_txt}" if risk_txt else "")),
        )
    if rule == "low_reviews":
        current = digits[0] if digits else 0
        return dict(
            kind_label=t("card.reviews"),
            headline=t("pain.low_reviews", n=current, min=MIN_REVIEWS),
            ruler_html=limit_ruler_html(
                current, MIN_REVIEWS,
                left_label=f"{current} {t('ruler.now')}",
                right_label=f"{t('ruler.goal')} {MIN_REVIEWS}",
                over_style=False),
            money=(f"{current} / {MIN_REVIEWS}"
                   + (f" · {risk_txt}" if risk_txt else "")),
        )
    if rule == "few_images":
        current = digits[0] if digits else 0
        return dict(
            kind_label=t("card.media"),
            headline=t("pain.few_images", n=current, min=MIN_IMAGES),
            ruler_html=limit_ruler_html(
                current, MIN_IMAGES,
                left_label=f"{current} {t('ruler.photos')}",
                right_label=f"{t('ruler.norm')} {MIN_IMAGES}+",
                over_style=False),
            money=(f"{current} / {MIN_IMAGES}"
                   + (f" · {risk_txt}" if risk_txt else "")),
        )
    if rule == "no_video":
        return dict(kind_label=t("card.media"), headline=t("pain.no_video"),
                    ruler_html="",
                    money=risk_txt or t("ruler.video_no"))
    if rule == "no_aplus":
        return dict(kind_label=t("card.content"), headline=t("pain.no_aplus"),
                    ruler_html="",
                    money=risk_txt or t("ruler.aplus_no"))
    if rule == "hard_to_scan":
        return dict(kind_label=t("card.title"),
                    headline=t("pain.hard_to_scan"),
                    ruler_html="", money=risk_txt or money)
    if rule == "empty_keywords":
        return dict(kind_label=t("card.attributes"),
                    headline=t("pain.empty_keywords"),
                    ruler_html="", money=risk_txt or money)
    if rule == "few_attributes":
        digits = [int(s) for s in str(r["pain"]).split() if s.isdigit()]
        cur_n = digits[0] if digits else 0
        tot_n = digits[1] if len(digits) > 1 else 27
        return dict(
            kind_label=t("card.attributes"),
            headline=f"{t('attr.filled')}: {cur_n}/{tot_n}",
            ruler_html=limit_ruler_html(cur_n, tot_n,
                                        left_label=f"{cur_n}",
                                        right_label=f"{t('ruler.norm')} {tot_n}",
                                        over_style=False),
            money=risk_txt or money)
    if rule == "no_shipping_template":
        return dict(kind_label=t("metric.shipping"),
                    headline=t("pain.no_shipping"),
                    ruler_html="", money=risk_txt or money)
    if rule == "low_ctr":
        nums = [s for s in str(r["pain"]).replace("%", " ").split()
                if s.replace(".", "").replace(",", "").isdigit()]
        imp = nums[0] if nums else "—"
        ctr = nums[1].replace(".", ",") if len(nums) > 1 else "—"
        return dict(
            kind_label=t("card.search"),
            headline=t("pain.low_ctr", imp=imp, ctr=ctr),
            ruler_html="", money=risk_txt or money)
    if rule == "out_of_stock":
        return dict(kind_label=t("card.stock"), headline=t("pain.out_of_stock"),
                    ruler_html="", money=risk_txt or money)
    return dict(kind_label=t("card.pain"), headline=str(r["pain"]),
                ruler_html="", money=money)


def render_pain(r: pd.Series, title_map: dict) -> None:
    asin, mp = r["asin"], r["marketplace"]
    product_title = title_map.get((asin, mp))
    fetched = fetch_map.get((asin, mp))
    fetched_label = (
        f"{t('matrix.collected_at')} {pd.to_datetime(fetched).strftime('%d.%m %H:%M')}"
        if fetched is not None and not pd.isna(fetched) else None
    )
    pain_card(
        severity=str(r["severity"]),
        asin=asin, marketplace=mp,
        product_title=product_title,
        image_url=image_map.get((asin, mp)),
        fetched_label=fetched_label,
        cause=cause_text(r), action=action_text(r),
        **build_card_args(r, product_title),
    )


# ---------------------------------------------------------------- страница
diag = load_diagnosis()
titles = load_titles()
title_map, image_map, fetch_map = {}, {}, {}
ECON = econ_map()
if not titles.empty:
    title_map = {(r["asin"], r["marketplace"]): r["title"]
                 for _, r in titles.iterrows()}
    image_map = {(r["asin"], r["marketplace"]): r.get("main_image")
                 for _, r in titles.iterrows()}
    fetch_map = {(r["asin"], r["marketplace"]): r.get("fetched_at")
                 for _, r in titles.iterrows()}

if diag.empty:
    st.info(t("common.no_data"))
    st.stop()

total_products, _ = load_scope()
added, closed = load_delta()
affected = diag.groupby(["asin", "marketplace"]).ngroups
run_label = pd.to_datetime(diag["created_at"].max()).strftime("%d.%m %H:%M")

def pain_money(row) -> float:
    """Деньги под риском по конкретной боли: выручка ASIN × коэффициент правила."""
    e = ECON.get((row["asin"], row["marketplace"]))
    if not e:
        return 0.0
    return money_at_risk(row.get("rule_id", ""), e.get("revenue_30d"))


diag = diag.copy()
diag["_money"] = diag.apply(pain_money, axis=1)
# по товару берём максимальный риск, а не сумму: проблемы пересекаются
total_risk = (diag.groupby(["asin", "marketplace"])["_money"].max().sum()
              if not diag.empty else 0.0)

risk_html = (
    f"{t('dash.at_risk')} <span style='color:#E8590C;font-weight:700;'>"
    f"€{total_risk:,.0f}</span>"
    if total_risk else
    f"{t('dash.at_risk')} <span style='color:#E8590C;font-weight:700;'>—</span> "
    f"<span style='color:#57534A;'>({t('common.no_revenue_data')})</span>"
).replace(",", " ")
delta_html = ""
if added or closed:
    delta_html = (
        f" · {t('dash.since_last')} <span style='color:#E8590C;font-weight:600;'>"
        f"+{added} {t('dash.new_pains')}</span> · {closed} {t('dash.closed_pains')}"
    )

headline = (f"{affected} {t('dash.need_attention')}"
            + (f" {t('dash.of')} {total_products}" if total_products else ""))
verdict(headline, risk_html + delta_html, meta_right=f"{t('dash.run')} {run_label}")

st.download_button(t("dash.fix_all_csv"),
                   diag.to_csv(index=False).encode("utf-8-sig"),
                   file_name="diagnosis.csv", mime="text/csv")

# ---- фильтры: severity и тип боли (компактные сегменты)
diag = diag.copy()
diag["_group"] = diag["rule_id"].map(RULE_GROUP).fillna("other")

s_counts = {s: int((diag["severity"] == s).sum()) for s in SEV_ORDER}
sev_opts = [s for s in ("red", "amber", "yellow") if s_counts[s]]
sev_labels = {"red": t("sev.red"), "amber": t("sev.amber"),
              "yellow": t("sev.yellow")}
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
             lambda g: f"{t('group.' + g)} {grp_counts[g]}", "grp_seg")

# ---- поиск, маркетплейсы, вид
q_col, mp_col, mode_col = st.columns([3, 2, 1.6])
query = q_col.text_input("Поиск", label_visibility="collapsed",
                         placeholder=t("list.search_pains"))
mps = sorted(diag["marketplace"].unique())
mp_sel = mp_col.multiselect("MP", mps, default=[], label_visibility="collapsed",
                            placeholder=t("list.all_mp"))
try:
    mode = mode_col.segmented_control(
        "Вид", ["cards", "table"], default="cards",
        format_func=lambda k: t("list.cards") if k == "cards" else t("list.table"),
        selection_mode="single", label_visibility="collapsed", key="diag_mode")
except AttributeError:
    mode = mode_col.radio("Вид", ["cards", "table"], horizontal=True,
                          format_func=lambda k: t("list.cards") if k == "cards" else t("list.table"),
                          label_visibility="collapsed", key="diag_mode")
mode = mode or "cards"

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
    st.caption(t("dash.no_by_filter"))
    st.stop()

view = view.copy()
view["_o"] = view["severity"].map(SEV_ORDER).fillna(9)
n_products = view.groupby(["asin", "marketplace"]).ngroups

# ---------------------------------------------------------------- вывод
if mode == "table":
    tbl = view.copy()
    # боли одного товара идут подряд; товары — по худшей боли, потом по числу болей
    prod = tbl.groupby(["asin", "marketplace"]).agg(
        _worst=("_o", "min"), _cnt=("_o", "size")).reset_index()
    tbl = tbl.merge(prod, on=["asin", "marketplace"], how="left")
    tbl = tbl.sort_values(["_worst", "_cnt", "asin", "_o"],
                          ascending=[True, False, True, True])

    tbl["prod"] = tbl.apply(
        lambda r: (r["sku_group"] if r["sku_group"] and r["sku_group"] != r["asin"]
                   else r["asin"]), axis=1)
    tbl["name"] = tbl.apply(
        lambda r: (title_map.get((r["asin"], r["marketplace"])) or "")[:60], axis=1)
    tbl["sev"] = tbl["severity"].map(
        {"red": "🔴", "amber": "🟠", "yellow": "🟡"})
    tbl["cnt"] = tbl["_cnt"]
    tbl["_group"] = tbl["_group"].map(lambda g: t(f"group.{g}"))
    tbl["pain"] = tbl.apply(
        lambda r: t(f"pain.{r['rule_id']}") if t(f"pain.{r['rule_id']}")
        != f"pain.{r['rule_id']}" else r["pain"], axis=1)
    tbl["action"] = tbl.apply(action_text, axis=1)
    tbl["link"] = tbl.apply(
        lambda r: f"https://www.amazon.{r['marketplace']}/dp/{r['asin']}", axis=1)
    tbl["risk"] = tbl["_money"].round(0)
    tbl["rev"] = tbl.apply(
        lambda r: (ECON.get((r["asin"], r["marketplace"])) or {}).get("revenue_30d"),
        axis=1)

    st.dataframe(
        tbl[["prod", "asin", "marketplace", "name", "cnt", "sev", "_group",
             "risk", "rev", "pain", "action", "link"]],
        column_config={
            "prod": st.column_config.TextColumn("SKU", width="small"),
            "asin": st.column_config.TextColumn("ASIN", width="small"),
            "marketplace": st.column_config.TextColumn("MP", width="small"),
            "name": st.column_config.TextColumn(t("card.title"), width="medium"),
            "cnt": st.column_config.NumberColumn(t("card.pain"), width="small"),
            "sev": st.column_config.TextColumn("!", width="small"),
            "_group": st.column_config.TextColumn(t("group.title"),
                                                  width="small"),
            "risk": st.column_config.NumberColumn(
                f"{t('dash.at_risk')}, EUR", format="%.0f", width="small"),
            "rev": st.column_config.NumberColumn(
                f"{t('metric.revenue')}, EUR", format="%.0f", width="small"),
            "pain": st.column_config.TextColumn(t("card.pain"), width="large"),
            "action": st.column_config.TextColumn(t("pain.fix_now"),
                                                  width="medium"),
            "link": st.column_config.LinkColumn(t("matrix.collect"),
                                                display_text="→"),
        },
        hide_index=True, use_container_width=True, height=560,
    )
    st.caption(
        f"{len(tbl)} {t('dash.pains_by_products')} {prod.shape[0]} · "
        f"{t('dash.rows_grouped')} · {t('list.sort_hint')}"
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
            "money": float(pd.to_numeric(g.get("_money"), errors="coerce").max() or 0),
        })
    # сначала по деньгам под риском, внутри — по тяжести
    groups.sort(key=lambda x: (-(x["money"] or 0), x["worst"]))

    pages = max(1, (len(groups) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(st.session_state.get("diag_page", 1), pages)
    chunk = groups[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]

    st.caption(f"{len(groups)} {t('dash.products_with_pains')} {len(chunk)}")

    for i, grp in enumerate(chunk):
        dots = " · ".join(
            f"{SEV_DOT[s]}{grp['counts'][s]}" for s in SEV_ORDER if grp["counts"][s]
        )
        ptitle = title_map.get((grp["asin"], grp["mp"])) or ""
        short = ptitle[:55] + ("…" if len(ptitle) > 55 else "")
        head = (f"{grp['sku']} · {grp['asin']}"
                if grp["sku"] and grp["sku"] != grp["asin"] else grp["asin"])
        _e = ECON.get((grp["asin"], grp["mp"])) or {}
        econ_part = ""
        if grp["money"]:
            econ_part = f" · {fmt_money(grp['money'])}"
        elif _e.get("sessions_30d"):
            econ_part = f" · {int(_e['sessions_30d'])} {t('common.sessions')}"
        label = (f"{head} · {grp['mp']} · {dots}{econ_part}"
                 + (f" · {short}" if short else ""))
        with st.expander(label, expanded=(i == 0 and page == 1)):
            for _, r in grp["rows"].sort_values(
                    ["_o", "created_at"], ascending=[True, False]).iterrows():
                render_pain(r, title_map)

    if pages > 1:
        p1, p2, p3 = st.columns([1, 2, 1])
        if p1.button(t("list.prev"), disabled=page <= 1):
            st.session_state["diag_page"] = page - 1
            st.rerun()
        p2.markdown(
            f"<div style='text-align:center;color:{MUTED};'>"
            f"{t('list.page')} {page} / {pages}</div>",
            unsafe_allow_html=True)
        if p3.button(t("list.next"), disabled=page >= pages):
            st.session_state["diag_page"] = page + 1
            st.rerun()

# ---- остальной каталог: здоровые отдельно от несобранных
if total_products:
    try:
        conn = get_conn()
        collected = pd.read_sql(
            "SELECT count(DISTINCT (asin, marketplace)) AS n "
            "FROM listing_snapshots WHERE ok = TRUE", conn).iloc[0]["n"]
        conn.close()
        collected = int(collected or 0)
    except Exception:
        collected = 0

    healthy = max(0, collected - affected)
    not_collected = max(0, total_products - collected)

    st.divider()
    parts = []
    if healthy:
        parts.append(f"<span style='color:#2F6B3A;'>✓ {healthy} "
                     f"{t('dash.healthy_products')}</span>")
    if not_collected:
        parts.append(f"<span style='color:{MUTED};'>○ {not_collected} "
                     f"{t('dash.not_collected_yet')}</span>")
    if parts:
        st.markdown(
            f"<div style='font-size:13px;'>{' · '.join(parts)}</div>",
            unsafe_allow_html=True)
    if not_collected:
        st.caption(t("dash.autocollect_hint"))
