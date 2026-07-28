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

from config import TITLE_LIMIT
from i18n import t
from services.db import get_conn
from components.ui import inject_fonts, eyebrow, limit_ruler_html

inject_fonts()

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

MIN_REVIEWS = 50
MIN_IMAGES = 7
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

    bsr_txt = str(info.get("Best Sellers Rank") or "")
    bsr = None
    m = re.findall(r"([\d,\.]+)\s+in\s+([^\(]+)", bsr_txt)
    if m:
        try:
            bsr = (int(m[-1][0].replace(",", "").replace(".", "")), m[-1][1].strip())
        except ValueError:
            bsr = None

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
        "coupon": bool(d.get("is_coupon_exists")),
    }


def health(mx: dict, is_comp: bool) -> tuple[str, str, str]:
    """Итоговое здоровье товара: (уровень, цвет, подпись)."""
    if is_comp:
        return "comp", MUTED, "конкурент"
    if not mx["in_stock"]:
        return "red", ERR_TEXT, "нет в наличии"
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
    if problems >= 3:
        return "amber", ACCENT, f"{problems} проблемы"
    if problems:
        return "yellow", WARN_TEXT, f"{problems} замечания"
    return "ok", OK_TEXT, "здоров"


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


st.header(t("nav.catalog"))
st.caption("Паспорт каждого товара: все метрики разом. Диагноз показывает только "
           "проблемные — здесь весь каталог, включая здоровых и конкурентов.")

df = load_catalog()
if df.empty:
    st.caption(t("common.no_data"))
    st.stop()

# ---- фильтры
f1, f2, f3 = st.columns([2, 2, 2])
who = f1.segmented_control(
    "кто", ["все", "наши", "конкуренты"], default="все",
    selection_mode="single", label_visibility="collapsed", key="cat_who") or "все"
mps = sorted(df["marketplace"].unique())
mp_sel = f2.multiselect("MP", mps, default=[], label_visibility="collapsed",
                        placeholder="Все маркетплейсы")
only_problems = f3.checkbox("Только с проблемами")

q = st.text_input("Поиск", label_visibility="collapsed",
                  placeholder="Поиск: ASIN, SKU или название...")

view = df
if who == "наши":
    view = view[~view["is_competitor"]]
elif who == "конкуренты":
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
    st.caption("Ничего не найдено по фильтрам.")
    st.stop()

order = {"red": 0, "amber": 1, "yellow": 2, "ok": 3, "comp": 4}
rows.sort(key=lambda x: (order[x["lvl"]], -(x["mx"]["title_len"] or 0)))

healthy = sum(1 for x in rows if x["lvl"] == "ok")
st.markdown(
    f"<div style='font-size:14px;color:{INK};margin-bottom:12px;'>"
    f"{len(rows)} товаров · <span style='color:{OK_TEXT};'>здоровых {healthy}</span>"
    f"</div>", unsafe_allow_html=True)

# ---- экспорт
exp = pd.DataFrame([{
    "sku": x["r"]["sku_group"], "asin": x["r"]["asin"], "mp": x["r"]["marketplace"],
    "кто": "конкурент" if x["r"]["is_competitor"] else "наш",
    "здоровье": x["label"], "тайтл_симв": x["mx"]["title_len"],
    "фото": x["mx"]["images"], "видео": x["mx"]["video"],
    "aplus": x["mx"]["aplus"], "отзывы": x["mx"]["reviews"],
    "рейтинг": x["mx"]["rating"], "цена": x["mx"]["price"],
    "bsr": x["mx"]["bsr"][0] if x["mx"]["bsr"] else None,
    "в_наличии": x["mx"]["in_stock"], "название": x["mx"]["title"],
} for x in rows])
st.download_button("Каталог → CSV", exp.to_csv(index=False).encode("utf-8-sig"),
                   file_name="catalog.csv", mime="text/csv")

# ---- пагинация
pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
page = min(st.session_state.get("cat_page", 1), pages)
chunk = rows[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]

# ---- карточки
for x in chunk:
    r, mx, color, label = x["r"], x["mx"], x["color"], x["label"]
    asin, mp = r["asin"], r["marketplace"]
    sku = r["sku_group"] if r["sku_group"] and r["sku_group"] != asin else ""
    head = f"{sku} · " if sku else ""
    who_lbl = t("common.competitor") if r["is_competitor"] else t("common.our")

    chips = "".join([
        chip("тайтл", f"{mx['title_len']}/{TITLE_LIMIT}",
             "err" if mx["title_len"] > TITLE_LIMIT else "ok"),
        chip("фото", str(mx["images"]),
             "ok" if mx["images"] >= MIN_IMAGES else "warn"),
        chip("видео", "есть" if mx["video"] else "нет",
             "ok" if mx["video"] else "warn"),
        chip("A+", "есть" if mx["aplus"] else "нет",
             "ok" if mx["aplus"] else "warn"),
        chip("отзывы", str(mx["reviews"] if mx["reviews"] is not None else "—"),
             "ok" if (mx["reviews"] or 0) >= MIN_REVIEWS else "warn"),
        chip("рейтинг", str(mx["rating"] or "—"),
             "ok" if (mx["rating"] or 0) >= 4.3 else "warn"),
        chip("цена", str(mx["price"] or "—"), "neutral"),
        chip("BSR", f"{mx['bsr'][0]}" if mx["bsr"] else "—", "neutral"),
        chip("сток", "в наличии" if mx["in_stock"] else "нет",
             "ok" if mx["in_stock"] else "err"),
    ])

    ruler = limit_ruler_html(
        mx["title_len"], TITLE_LIMIT, left_label=f"{TITLE_LIMIT}",
        right_label=(f"+{mx['title_len'] - TITLE_LIMIT} резать"
                     if mx["title_len"] > TITLE_LIMIT
                     else f"свободно {TITLE_LIMIT - mx['title_len']}"),
    ) if mx["title_len"] else ""

    fetched = (pd.to_datetime(r["fetched_at"]).strftime("%d.%m %H:%M")
               if pd.notna(r["fetched_at"]) else "не собирался")
    short = (mx["title"][:130] + "…") if len(mx["title"]) > 130 else mx["title"]

    st.markdown(
        f"""
        <div style="background:{CARD};border:1px solid {BORDER};
                    border-left:3px solid {color};border-radius:0 12px 12px 0;
                    padding:14px 18px;margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;align-items:baseline;">
            {eyebrow(f"{head}<a href='https://www.amazon.{mp}/dp/{asin}' target='_blank' style='color:{MUTED};'>{asin}</a> · {mp} · {who_lbl}")}
            <span style="font-family:{MONO};font-size:12px;color:{color};">{label} · {fetched}</span>
          </div>
          <div style="font-size:13px;color:{INK};margin:6px 0 8px;">{short or "— нет данных"}</div>
          {ruler}
          <div style="margin-top:6px;">{chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

if pages > 1:
    p1, p2, p3 = st.columns([1, 2, 1])
    if p1.button("← Назад", disabled=page <= 1):
        st.session_state["cat_page"] = page - 1
        st.rerun()
    p2.markdown(f"<div style='text-align:center;color:{MUTED};'>стр. {page} / {pages}</div>",
                unsafe_allow_html=True)
    if p3.button("Вперёд →", disabled=page >= pages):
        st.session_state["cat_page"] = page + 1
        st.rerun()
