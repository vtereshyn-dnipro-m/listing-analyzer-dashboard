# -*- coding: utf-8 -*-
"""
pages/catalog.py — Каталог: паспорт каждого товара.

Одна карточка = один товар со всеми метриками разом: тайтл, фото, видео,
A+, отзывы, рейтинг, цена, BSR, сток, продавец. Здоровье считает код.
Показываются ВСЕ товары (включая здоровых и конкурентов) — в отличие от
Диагноза, который показывает только проблемные.
"""
from __future__ import annotations

import json
import re

import pandas as pd
import streamlit as st

from config import TITLE_LIMIT as _TL_DEFAULT
from i18n import t
from services.db import get_conn
from services.settings import get_int, get_float
from services.economics import econ_map, fmt_money, fmt_conversion
from services.worklog import worklog_map, work_badges
from services.attributes import (
    attrs_map, missing_critical, fill_state, node_short,
)
from services.search import (
    search_map, fmt_int, fmt_pct, ctr_state,
)
from components.ui import inject_fonts, eyebrow, limit_ruler_html

inject_fonts()
st.title(t("nav.catalog"))

INK = "#1A1815"
MUTED = "#8A8578"
BORDER = "#E7E4DD"
CARD = "#FFFFFF"
ACCENT = "#E8590C"
OK_BG = "#DCEEE0"
OK_TEXT = "#2F6B3A"
WARN_BG = "#FAEEDA"
WARN_TEXT = "#854F0B"
ERR_BG = "#FCEBEB"
ERR_TEXT = "#A32D2D"
MONO = '"JetBrains Mono","SFMono-Regular",Consolas,monospace'

TITLE_LIMIT = get_int("limit.title", _TL_DEFAULT)
MIN_REVIEWS = get_int("threshold.min_reviews", 50)
CRIT_REVIEWS = 10
RATING_RED = get_float("threshold.rating_red", 4.3)
RATING_GREEN = get_float("threshold.rating_green", 4.4)
MIN_IMAGES = get_int("threshold.min_images", 7)
PAGE_SIZE = 20


@st.cache_data(ttl=300)
def load_catalog() -> pd.DataFrame:
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT m.sku_group, m.asin, m.marketplace, m.is_competitor,
                   s.fetched_at, s.ok, s.title, s.in_stock, s.review_count, s.raw
            FROM product_matrix m
            LEFT JOIN LATERAL (
                SELECT fetched_at, ok, title, in_stock, review_count, raw
                FROM listing_snapshots s
                WHERE s.asin = m.asin AND s.marketplace = m.marketplace
                  AND s.ok = TRUE
                ORDER BY s.fetched_at DESC LIMIT 1
            ) s ON TRUE
            ORDER BY m.is_competitor, m.sku_group, m.asin
            """,
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def _raw(v) -> dict:
    try:
        return v if isinstance(v, dict) else json.loads(v or "{}")
    except Exception:
        return {}


def metrics(row: pd.Series) -> dict:
    """Все метрики товара из последнего снапшота."""
    d = _raw(row.get("raw"))
    info = d.get("product_information") or {}

    imgs = d.get("images") or d.get("images_of_specified_asin") or []
    ids = set()
    for u in imgs:
        if isinstance(u, str):
            ids.add(u.rsplit("/I/", 1)[-1].split(".")[0])

    # BSR: ключ и формат зависят от языка страницы
    bsr_txt = ""
    for k, v in info.items():
        if re.search(r"best.?sellers|clasificaci|bestseller|classement|"
                     r"posizione|migliori|rank", str(k), re.I):
            bsr_txt = str(v)
            break
    bsr = None
    if bsr_txt:
        clean = re.sub(r"\([^)]*\)", " ", bsr_txt)   # убрать "(Ver el Top 100 ...)"
        m = re.findall(
            r"(?:n[ºo°]\s*|nr\.?\s*)?([\d][\d.,]*)\s+(?:in|en|dans|nella|di)\s+"
            r"([^,;]+?)(?=\s*(?:n[ºo°]\s*[\d]|nr\.?\s*[\d]|[\d]+\s+(?:in|en)\s|$))",
            clean, re.I)
        if m:
            try:
                bsr = (int(re.sub(r"[^\d]", "", m[-1][0])), m[-1][1].strip(" ,.·"))
            except ValueError:
                bsr = None

    main_img = d.get("main_image") or (imgs[0] if imgs else "")

    price = d.get("price") or ""
    try:
        rating = float(str(d.get("average_rating") or "").replace(",", "."))
    except ValueError:
        rating = None

    title = row.get("title") or ""
    return {
        "title": title,
        "title_len": len(title),
        "images": len(ids),
        "video": int(d.get("number_of_videos") or 0),
        "aplus": bool(d.get("aplus")),
        "reviews": row.get("review_count"),
        "rating": rating,
        "price": price,
        "bsr": bsr,
        "in_stock": bool(row.get("in_stock")),
        "seller": d.get("sold_by") or "",
        "econ": {},
        "main_img": main_img,
        "coupon": bool(d.get("is_coupon_exists")),
    }


def health(mx: dict, is_comp: bool) -> tuple[str, str, str]:
    """Итоговое здоровье товара: (уровень, цвет, подпись)."""
    if is_comp:
        return "comp", MUTED, t("common.competitor")
    if not mx["in_stock"]:
        return "red", ERR_TEXT, t("catalog.h_nostock")
    problems = 0
    if mx["title_len"] > TITLE_LIMIT:
        problems += 1
    if mx["images"] and mx["images"] < MIN_IMAGES:
        problems += 1
    if not mx["video"]:
        problems += 1
    if not mx["aplus"]:
        problems += 1
    if mx["reviews"] is not None and mx["reviews"] < MIN_REVIEWS:
        problems += 1
    if mx["rating"] is not None and mx["rating"] < RATING_RED:
        problems += 1
    if problems >= 3:
        return "amber", ACCENT, f"{problems} {t('catalog.h_problems')}"
    if problems:
        return "yellow", WARN_TEXT, f"{problems} {t('catalog.h_notes')}"
    return "ok", OK_TEXT, t("catalog.h_ok")


def chip(label: str, value: str, state: str) -> str:
    bg, fg = {
        "ok": (OK_BG, OK_TEXT),
        "warn": (WARN_BG, WARN_TEXT),
        "err": (ERR_BG, ERR_TEXT),
        "neutral": ("#F1EFE8", MUTED),
    }[state]
    return (
        f"<span style='display:inline-block;background:{bg};color:{fg};"
        f"border-radius:8px;padding:4px 10px;margin:0 6px 6px 0;font-size:12px;'>"
        f"<span style='opacity:.7;'>{label}</span> "
        f"<b style='font-family:{MONO};'>{value}</b></span>"
    )


st.caption(t("catalog.caption"))

ECON = econ_map()
WORK = worklog_map()
SEARCH = search_map()
ATTRS = attrs_map()
df = load_catalog()
if df.empty:
    st.caption(t("common.no_data"))
    st.stop()

# ---- фильтры
f1, f2, f3 = st.columns([2, 2, 2])
_who_opts = ["all", "ours", "comp"]
_who_lbl = {"all": t("catalog.all"), "ours": t("catalog.ours"),
            "comp": t("catalog.competitors")}
who = f1.segmented_control(
    "кто", _who_opts, default="all", format_func=lambda k: _who_lbl[k],
    selection_mode="single", label_visibility="collapsed", key="cat_who") or "all"
mps = sorted(df["marketplace"].unique())
mp_sel = f2.multiselect("MP", mps, default=[], label_visibility="collapsed",
                        placeholder=t("list.all_mp"))
only_problems = f3.checkbox(t("catalog.only_problems"))

qc, vc = st.columns([4, 1.6])
q = qc.text_input("Поиск", label_visibility="collapsed",
                  placeholder=t("catalog.search"))
try:
    mode = vc.segmented_control(
        "Вид", ["cards", "table"], default="cards",
        format_func=lambda k: t("list.cards") if k == "cards" else t("list.table"),
        selection_mode="single", label_visibility="collapsed", key="cat_mode")
except AttributeError:
    mode = vc.radio("Вид", ["cards", "table"], horizontal=True,
                    format_func=lambda k: t("list.cards") if k == "cards" else t("list.table"),
                    label_visibility="collapsed", key="cat_mode")
mode = mode or "cards"

view = df
if who == "ours":
    view = view[~view["is_competitor"]]
elif who == "comp":
    view = view[view["is_competitor"]]
if mp_sel:
    view = view[view["marketplace"].isin(mp_sel)]
if q.strip():
    ql = q.strip().lower()
    view = view[
        view["asin"].str.lower().str.contains(ql, na=False)
        | view["sku_group"].astype(str).str.lower().str.contains(ql, na=False)
        | view["title"].astype(str).str.lower().str.contains(ql, na=False)
    ]

rows = []
for _, r in view.iterrows():
    mx = metrics(r)
    lvl, color, label = health(mx, bool(r["is_competitor"]))
    rows.append({"r": r, "mx": mx, "lvl": lvl, "color": color, "label": label})

if only_problems:
    rows = [x for x in rows if x["lvl"] in ("red", "amber", "yellow")]

if not rows:
    st.caption(t("catalog.nothing"))
    st.stop()

order = {"red": 0, "amber": 1, "yellow": 2, "ok": 3, "comp": 4}
def _rev(x) -> float:
    e = ECON.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
    try:
        return float(e.get("revenue_30d") or 0)
    except (TypeError, ValueError):
        return 0.0


rows.sort(key=lambda x: (order[x["lvl"]], -_rev(x),
                         -(x["mx"]["title_len"] or 0)))

healthy = sum(1 for x in rows if x["lvl"] == "ok")
st.markdown(
    f"<div style='font-size:14px;color:{INK};margin-bottom:12px;'>"
    f"{len(rows)} {t('catalog.products')} · <span style='color:{OK_TEXT};'>"
    f"{t('catalog.healthy')} {healthy}</span>"
    f"</div>", unsafe_allow_html=True)

# ---- экспорт
exp = pd.DataFrame([{
    "sku": x["r"]["sku_group"], "asin": x["r"]["asin"],
    "mp": x["r"]["marketplace"],
    "who": ("competitor" if x["r"]["is_competitor"] else "own"),
    "health": x["label"], "title_len": x["mx"]["title_len"],
    "photos": x["mx"]["images"], "video": x["mx"]["video"],
    "aplus": x["mx"]["aplus"], "reviews": x["mx"]["reviews"],
    "rating": x["mx"]["rating"], "price": x["mx"]["price"],
    "bsr": x["mx"]["bsr"][0] if x["mx"]["bsr"] else None,
    "in_stock": x["mx"]["in_stock"], "name": x["mx"]["title"],
    "revenue_30d": (ECON.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                    ).get("revenue_30d"),
    "sessions_30d": (ECON.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                     ).get("sessions_30d"),
    "shipping_template": (ECON.get((x["r"]["asin"], x["r"]["marketplace"]))
                          or {}).get("shipping_template"),
    "sqp_queries": (SEARCH.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                    ).get("queries"),
    "sqp_demand": (SEARCH.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                   ).get("demand"),
    "sqp_imp_share": (SEARCH.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                      ).get("imp_share"),
    "sqp_ctr": (SEARCH.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                ).get("ctr"),
    "category": (ATTRS.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                 ).get("browse_node_name"),
    "category_path": (ATTRS.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                      ).get("browse_path"),
    "attrs_filled": (ATTRS.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                     ).get("attrs_filled"),
    "attrs_empty": (ATTRS.get((x["r"]["asin"], x["r"]["marketplace"])) or {}
                    ).get("attrs_empty"),
} for x in rows])
st.download_button(t("catalog.export"), exp.to_csv(index=False).encode("utf-8-sig"),
                   file_name="catalog.csv", mime="text/csv")

# ---- пагинация
pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
page = min(st.session_state.get("cat_page", 1), pages)
chunk = rows[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]

# ---- таблица
if mode == "table":
    tv = exp.copy()
    tv["img"] = [x["mx"]["main_img"] for x in rows]
    tv["link"] = [f"https://www.amazon.{x['r']['marketplace']}/dp/{x['r']['asin']}"
                  for x in rows]
    tv["bsr_cat"] = [x["mx"]["bsr"][1] if x["mx"]["bsr"] else "" for x in rows]
    tv = tv.rename(columns={"title_len": "len", "in_stock": "stock",
                            "revenue_30d": "rev", "sessions_30d": "sess",
                            "shipping_template": "ship"})
    cols = [c for c in ["img", "sku", "asin", "mp", "who", "health", "len",
                        "photos", "video", "aplus", "reviews", "rating",
                        "price", "bsr", "bsr_cat", "stock", "rev", "sess",
                        "ship", "name", "link"] if c in tv.columns]
    st.dataframe(
        tv[cols],
        column_config={
            "img": st.column_config.ImageColumn(t("metric.photos"),
                                                width="small"),
            "sku": st.column_config.TextColumn("SKU", width="small"),
            "asin": st.column_config.TextColumn("ASIN", width="small"),
            "mp": st.column_config.TextColumn("MP", width="small"),
            "who": st.column_config.TextColumn(t("common.our"), width="small"),
            "health": st.column_config.TextColumn(t("catalog.h_ok"),
                                                  width="small"),
            "len": st.column_config.NumberColumn(t("metric.title"),
                                                 width="small"),
            "photos": st.column_config.NumberColumn(t("metric.photos"),
                                                    width="small"),
            "video": st.column_config.TextColumn(t("metric.video"),
                                                 width="small"),
            "aplus": st.column_config.TextColumn(t("metric.aplus"),
                                                 width="small"),
            "reviews": st.column_config.NumberColumn(t("metric.reviews"),
                                                     width="small"),
            "rating": st.column_config.NumberColumn(t("metric.rating"),
                                                    width="small"),
            "price": st.column_config.TextColumn(t("metric.price"),
                                                 width="small"),
            "bsr": st.column_config.NumberColumn("BSR", width="small"),
            "bsr_cat": st.column_config.TextColumn("BSR cat", width="small"),
            "stock": st.column_config.TextColumn(t("metric.stock"),
                                                 width="small"),
            "rev": st.column_config.NumberColumn(
                f"{t('metric.revenue')}, EUR", format="%.0f", width="small"),
            "sess": st.column_config.NumberColumn(t("metric.sessions"),
                                                  width="small"),
            "ship": st.column_config.TextColumn(t("metric.shipping"),
                                                width="medium"),
            "name": st.column_config.TextColumn(t("card.title"), width="large"),
            "link": st.column_config.LinkColumn(t("matrix.collect"),
                                                display_text="→"),
        },
        hide_index=True, use_container_width=True, height=560,
    )
    st.caption(t("list.sort_hint"))
    st.stop()

# ---- карточки
for x in chunk:
    r, mx, color, label = x["r"], x["mx"], x["color"], x["label"]
    asin, mp = r["asin"], r["marketplace"]
    sku = r["sku_group"] if r["sku_group"] and r["sku_group"] != asin else ""
    head = f"{sku} · " if sku else ""
    who_lbl = t("common.competitor") if r["is_competitor"] else t("common.our")

    _ec = ECON.get((asin, mp)) or {}
    _badges = work_badges(WORK.get((asin, mp)))
    _sr = SEARCH.get((asin, mp)) or {}
    _at = ATTRS.get((asin, mp)) or {}
    _fill_st, _fill_label = fill_state(_at)
    _miss = missing_critical(_at)
    chips = "".join([
        chip(t("metric.title"), f"{mx['title_len']}/{TITLE_LIMIT}",
             "err" if mx["title_len"] > TITLE_LIMIT else "ok"),
        chip(t("metric.photos"), str(mx["images"]),
             "ok" if mx["images"] >= MIN_IMAGES else "warn"),
        chip(t("metric.video"), t("metric.yes") if mx["video"] else t("metric.no"),
             "ok" if mx["video"] else "warn"),
        chip(t("metric.aplus"), t("metric.yes") if mx["aplus"] else t("metric.no"),
             "ok" if mx["aplus"] else "warn"),
        chip(t("metric.reviews"), str(mx["reviews"] if mx["reviews"] is not None else "—"),
             "ok" if (mx["reviews"] or 0) >= MIN_REVIEWS
             else ("err" if (mx["reviews"] or 0) < CRIT_REVIEWS else "warn")),
        chip(t("metric.rating"),
             (f"{mx['rating']:.1f}".replace(".", ",") if mx["rating"] else "—"),
             "neutral" if not mx["rating"]
             else ("err" if mx["rating"] < RATING_RED
                   else ("ok" if mx["rating"] >= RATING_GREEN else "warn"))),
        chip(t("metric.price"), str(mx["price"] or "—"), "neutral"),
        chip(t("metric.bsr"), (f"#{mx['bsr'][0]} · {mx['bsr'][1][:22]}"
                     if mx["bsr"] else "—"), "neutral"),
        chip(t("metric.stock"), t("metric.in_stock") if mx["in_stock"] else t("metric.no"),
             "ok" if mx["in_stock"] else "err"),
    ] + ([
        chip(t("metric.revenue"), fmt_money(_ec.get("revenue_30d"), ""),
             "neutral"),
        chip(t("metric.sessions"), str(int(_ec.get("sessions_30d") or 0)),
             "neutral"),
        chip(t("metric.conversion"), fmt_conversion(_ec.get("conversion_rate")),
             "ok" if float(_ec.get("conversion_rate") or 0) > 0 else "neutral"),
        chip(t("metric.shipping"),
             str(_ec.get("shipping_template") or t("metric.no_template"))[:22],
             "ok" if _ec.get("shipping_template") else "warn"),
    ] if _ec else []) + ([
        chip(t("search.queries"), fmt_int(_sr.get("queries")), "neutral"),
        chip(t("search.demand"), fmt_int(_sr.get("demand")), "neutral"),
        chip(t("search.imp_share"), fmt_pct(_sr.get("imp_share")),
             "ok" if (_sr.get("imp_share") or 0) >= 1 else "warn"),
        chip("CTR", fmt_pct(_sr.get("ctr")),
             {"ok": "ok", "warn": "err", "none": "neutral"}[ctr_state(_sr)]),
        chip(t("search.purchases"), fmt_int(_sr.get("purchases")),
             "ok" if (_sr.get("purchases") or 0) > 0 else "warn"),
    ] if _sr else []) + ([
        chip(t("attr.category"), node_short(_at), "neutral"),
        chip(t("attr.filled"), _fill_label,
             {"ok": "ok", "warn": "warn", "err": "err",
              "none": "neutral"}[_fill_st]),
    ] + ([chip(t("attr.missing"), ", ".join(_miss[:3]), "warn")]
         if _miss else []) if _at else []))

    ruler = limit_ruler_html(
        mx["title_len"], TITLE_LIMIT, left_label=f"{TITLE_LIMIT}",
        right_label=(f"+{mx['title_len'] - TITLE_LIMIT} резать"
                     if mx["title_len"] > TITLE_LIMIT
                     else f"свободно {TITLE_LIMIT - mx['title_len']}"),
    ) if mx["title_len"] else ""

    fetched = (pd.to_datetime(r["fetched_at"]).strftime("%d.%m %H:%M")
               if pd.notna(r["fetched_at"]) else t("catalog.not_collected"))
    short = (mx["title"][:130] + "…") if len(mx["title"]) > 130 else mx["title"]

    st.markdown(
        f"""
        <div style="background:{CARD};border:1px solid {BORDER};
                    border-left:3px solid {color};border-radius:0 12px 12px 0;
                    padding:14px 18px;margin-bottom:10px;display:flex;gap:16px;">
          <div style="flex:0 0 92px;">
            {f'<img src="{mx["main_img"]}" style="width:92px;height:92px;object-fit:contain;background:#fff;border:1px solid {BORDER};border-radius:10px;">' if mx["main_img"] else ''}
          </div>
          <div style="flex:1;min-width:0;">
          <div style="display:flex;justify-content:space-between;align-items:baseline;">
            {eyebrow(f"{head}<a href='https://www.amazon.{mp}/dp/{asin}' target='_blank' style='color:{MUTED};'>{asin}</a> · {mp} · {who_lbl}")}
            <span style='font-family:{MONO};font-size:12px;color:{color};'>{label} · {fetched}</span>
          </div>
          <div style="font-size:13px;color:{INK};margin:6px 0 8px;">{short or t("catalog.no_data_row")}</div>
          {ruler}
          <div style="margin-top:6px;">{chips}</div>
          {('<div style="margin-top:6px;">' + _badges + '</div>') if _badges else ''}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

if pages > 1:
    p1, p2, p3 = st.columns([1, 2, 1])
    if p1.button(t("list.prev"), disabled=page <= 1):
        st.session_state["cat_page"] = page - 1
        st.rerun()
    p2.markdown(f"<div style='text-align:center;color:{MUTED};'>"
                f"{t('list.page')} {page} / {pages}</div>",
                unsafe_allow_html=True)
    if p3.button(t("list.next"), disabled=page >= pages):
        st.session_state["cat_page"] = page + 1
        st.rerun()
