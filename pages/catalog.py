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
from services.issues import (
    issues_map, asin_index, family_map, extract_deadline, MONITORED,
    cause_label, code_label, fmt_issue_date,
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
MONO = "var(--ls-mono)"   # переменная из inject_fonts(): без кавычек в атрибутах

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
    """Все метрики товара из последнего снапшота.

    ВАЖНО: у товара, который ещё ни разу не собирался, LEFT JOIN LATERAL
    в load_catalog() отдаёт NULL по всем полям снапшота -> в pandas это
    NaN (float). `row.get("x") or ""` NaN не ловит, потому что bool(NaN)
    равен True — поэтому все "сырые" поля явно проверяются через pd.isna().
    """
    d = _raw(row.get("raw"))
    info = d.get("product_information") or {}

    collected = pd.notna(row.get("fetched_at"))

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

    raw_title = row.get("title")
    title = "" if pd.isna(raw_title) else str(raw_title)

    raw_reviews = row.get("review_count")
    reviews = None if pd.isna(raw_reviews) else int(raw_reviews)

    raw_stock = row.get("in_stock")
    in_stock = False if pd.isna(raw_stock) else bool(raw_stock)

    return {
        "title": title,
        "title_len": len(title),
        "images": len(ids),
        "video": int(d.get("number_of_videos") or 0),
        "aplus": bool(d.get("aplus")),
        "reviews": reviews,
        "rating": rating,
        "price": price,
        "bsr": bsr,
        "in_stock": in_stock,
        "seller": d.get("sold_by") or "",
        "econ": {},
        "main_img": main_img,
        "coupon": bool(d.get("is_coupon_exists")),
        "collected": collected,
    }


def health(mx: dict, is_comp: bool) -> tuple[str, str, str]:
    """Итоговое здоровье товара: (уровень, цвет, подпись)."""
    if is_comp:
        return "comp", MUTED, t("common.competitor")
    if not mx["collected"]:
        return "gray", MUTED, t("catalog.h_not_collected")
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
ISSUES = issues_map()
AIDX = asin_index(ISSUES)
FAMILY = family_map(ISSUES)
df = load_catalog()
if df.empty:
    st.caption(t("common.no_data"))
    st.stop()

# ---- фильтры
f1, f2, f3, f4 = st.columns([1.8, 1.6, 1.4, 2.4])
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

# фильтр по Amazon Issues: все / с проблемами / снятые с продажи
_iss_opts = ["all", "problems", "blocked"]
_iss_lbl = {"all": t("issue.f_all"), "problems": t("issue.f_problems"),
            "blocked": t("issue.f_blocked")}
try:
    iss_f = f4.segmented_control(
        "issues", _iss_opts, default="all",
        format_func=lambda k: _iss_lbl[k], selection_mode="single",
        label_visibility="collapsed", key="cat_issues")
except AttributeError:
    iss_f = f4.radio("issues", _iss_opts, horizontal=True,
                     format_func=lambda k: _iss_lbl[k],
                     label_visibility="collapsed", key="cat_issues")
iss_f = iss_f or "all"


def _pair_state(asin: str, mp: str) -> str:
    """Состояние конкретной пары товар × рынок — не худшее по всем рынкам:
    иначе заблокированный на IT ASIN попадал в «Не продаются» и на живом ES."""
    return (ISSUES.get((str(asin), str(mp).lower())) or {"state": "none"})["state"]

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
if iss_f == "problems":
    view = view[[_pair_state(a, m) != "none"
                 for a, m in zip(view["asin"], view["marketplace"])]]
elif iss_f == "blocked":
    view = view[[_pair_state(a, m) == "blocked"
                 for a, m in zip(view["asin"], view["marketplace"])]]

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

order = {"red": 0, "amber": 1, "yellow": 2, "ok": 3, "gray": 4, "comp": 5}
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

# ---- плашка Amazon Issues
def issue_details(entries: list, group_sku: str = "") -> None:
    """Раскрытие плашки: по каждому рынку — ASIN-ссылка на листинг,
    состояние, коды, тексты Amazon. ASIN обязателен: у одного SKU на
    разных рынках он может отличаться. SKU рынка показывается, когда
    отличается от группового — чинить в Seller Central придётся по нему."""
    for m, s in entries:
        asin_link = (
            f'<a href="https://www.amazon.{m}/dp/{s["asin"]}" target="_blank" '
            f'style="font-family:{MONO};color:{INK};">{s["asin"]}</a>'
        ) if s.get("asin") else ""
        if s["state"] == "blocked":
            state_txt = "🔴 " + t("issue.blocked_since",
                                  date=fmt_issue_date(s["first_seen"],
                                                      with_year=True))
        else:
            state_txt = f"🟡 {t('issue.mp_selling')}"
        head = f"<b>{str(m).upper()}</b>"
        if asin_link:
            head += f" · {asin_link}"
        head += f" — {state_txt}"
        if s["stock"] is not None:
            head += " · " + t("issue.stock_n", n=s["stock"])
        mkt_sku = s.get("sku") or ""
        if mkt_sku and mkt_sku != group_sku:
            head += f' · SKU <span class="ls-mono">{mkt_sku}</span>'
        if not s["had_sales"]:
            head += " · " + t("issue.never_sold")
        st.markdown(head, unsafe_allow_html=True)

        # состояние семейства вариантов: покупатель на странице Amazon
        # видит живые соседние варианты и может решить, что система ошиблась
        if s["state"] == "blocked":
            fam = FAMILY.get((s.get("asin", ""), m))
            if fam and fam["total"] >= 2:
                fam_txt = (t("issue.family_all_blocked")
                           if fam["blocked"] >= fam["total"]
                           else t("issue.family_partial",
                                  blocked=fam["blocked"], total=fam["total"]))
                st.markdown(
                    f'<div style="font-size:12.5px;color:{WARN_TEXT};'
                    f'margin:-4px 0 6px;">↳ {fam_txt}</div>',
                    unsafe_allow_html=True)
        for row in s["rows"]:
            line = (f"`{row['code']}` **{code_label(row['code'])}** · "
                    + t("issue.since_date",
                        date=fmt_issue_date(row["first_seen"], with_year=True)))
            if row["attributes"]:
                line += f" · {t('issue.attributes')}: {row['attributes']}"
            st.markdown(line)
            if row["message"]:
                st.caption(row["message"])

    # пояснение один раз под раскрытием — только когда у какого-то из
    # заблокированных рынков есть живые варианты: иначе «они продаются» — ложь
    def _fam(m: str, s: dict) -> dict:
        return FAMILY.get((s.get("asin", ""), m)) or {}

    if any(s["state"] == "blocked"
           and 0 < _fam(m, s).get("blocked", 0) < _fam(m, s).get("total", 0)
           for m, s in entries):
        st.caption(t("issue.family_note"))


def issue_plate(asin: str, mp: str,
                group_sku: str = "") -> tuple[str, str | None, dict | None]:
    """Плашка Amazon Issues ВНУТРЬ карточки: (html, цвет кромки, сводка).

    Состояние — только СВОЕГО рынка (заблокированный на IT не красит живой
    ES). Первая строка — состояние и причина, жирная; вторая — контекст
    серым: остаток, SKU рынка (если отличается от группового), семейство
    вариантов, дедлайн из текста Amazon и что на других рынках. Серая
    плашка на немониторимом рынке обязательна: без неё отсутствие проблем
    неотличимо от отсутствия данных."""
    own = ISSUES.get((asin, mp))
    entries = AIDX.get(asin) or []

    # «также: FR (там продаётся), IT (там снят)» — состояние каждой пары
    others = [(str(m).upper(),
               t("issue.also_blocked", mp=str(m).upper())
               if s["state"] == "blocked"
               else t("issue.also_alive", mp=str(m).upper()))
              for m, s in entries if s["state"] != "none" and m != mp]
    also = (t("issue.also_markets",
              mps=", ".join(txt for _, txt in sorted(others)))
            if others else "")

    if not own or own["state"] == "none":
        if mp not in MONITORED:
            html = (
                f'<div style="background:#F1EFE8;border-radius:8px;'
                f'padding:6px 12px;margin:6px 0 8px;font-size:12px;'
                f'color:{MUTED};">◦ {t("issue.not_monitored")}</div>'
            )
            return html, None, None
        return "", None, None

    ctx: list[str] = []
    if own["state"] == "warning":
        dl = extract_deadline(own)
        if dl:
            what, ts = dl
            part = t("issue.deadline_until", what=what,
                     date=ts.strftime("%d.%m"))
            if ts < pd.Timestamp.now(tz="UTC"):
                part += " · " + t("issue.deadline_passed")
            ctx.append(part)
    if own["stock"] is not None:
        ctx.append(t("issue.stock_n", n=own["stock"]))
    mkt_sku = own.get("sku") or ""
    if mkt_sku and mkt_sku != group_sku:
        ctx.append(f'SKU <span class="ls-mono">{mkt_sku}</span>')
    fam = FAMILY.get((asin, mp))
    if fam and fam["total"] >= 2:
        ctx.append(t("issue.family_short_all")
                   if fam["blocked"] >= fam["total"]
                   else t("issue.family_short_partial",
                          blocked=fam["blocked"], total=fam["total"]))
    if not own["had_sales"]:
        ctx.append(t("issue.never_sold"))
    if also:
        ctx.append(also)

    if own["state"] == "blocked":
        bg, fg = ERR_BG, ERR_TEXT
        line1 = ("🔴 " + t("issue.blocked_since",
                           date=fmt_issue_date(own["first_seen"]))
                 + " · " + cause_label(own["cause"] or None))
        edge = ERR_TEXT
    else:
        bg, fg = WARN_BG, WARN_TEXT
        line1 = "🟡 " + t("issue.selling_warnings", n=len(own["rows"]))
        edge = ACCENT

    # вторая строка не рендерится пустой: пустая подстановка одна на
    # строке закрывает HTML-блок (правило 1)
    line2 = (f'<div style="font-size:12px;color:#57534A;margin-top:2px;">'
             f'{" · ".join(ctx)}</div>') if ctx else ""
    html = (
        f'<div style="background:{bg};border-radius:8px;padding:8px 12px;'
        f'margin:6px 0 8px;font-size:13px;">'
        f'<div style="font-weight:700;color:{fg};">{line1}</div>'
        f"{line2}</div>"
    )
    return html, edge, own


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
        right_label=(f"+{mx['title_len'] - TITLE_LIMIT} {t('ruler.cut')}"
                     if mx["title_len"] > TITLE_LIMIT
                     else f"{t('ruler.free')} {TITLE_LIMIT - mx['title_len']}"),
    ) if mx["title_len"] else ""

    fetched = (pd.to_datetime(r["fetched_at"]).strftime("%d.%m %H:%M")
               if pd.notna(r["fetched_at"]) else t("catalog.not_collected"))
    short = (mx["title"][:130] + "…") if len(mx["title"]) > 130 else mx["title"]

    thumb = (
        f'<img src="{mx["main_img"]}" style="width:92px;height:92px;'
        f'object-fit:contain;background:#fff;border:1px solid {BORDER};'
        f'border-radius:10px;">'
    ) if mx["main_img"] else ""
    head_html = eyebrow(
        f'{head}<a href="https://www.amazon.{mp}/dp/{asin}" target="_blank" '
        f'style="color:{MUTED};">{asin}</a> · {mp} · {who_lbl}'
    )
    badges_html = (f'<div style="margin-top:6px;">{_badges}</div>'
                   if _badges else "")

    # Amazon Issues — только свои товары: реплика идёт из аккаунта продавца,
    # по конкурентам этих данных не бывает. Плашка внутри карточки, кромка
    # перекрашивается: blocked/warning ловятся глазом при прокрутке.
    plate_html, edge, own_issues = ("", None, None)
    if not r["is_competitor"]:
        plate_html, edge, own_issues = issue_plate(
            asin, mp, str(r["sku_group"] or ""))

    # HTML одной строкой: у карточки может не быть линейки, значков или
    # плашки, и на переносах пустые участки превращаются в блок кода markdown.
    st.markdown(
        f'<div class="ls-card" style="background:{CARD};'
        f'border:1px solid {BORDER};border-left:4px solid {edge or color};'
        f'border-radius:0 12px 12px 0;padding:14px 18px;margin-bottom:10px;'
        f'display:flex;gap:16px;">'
        f'<div style="flex:0 0 92px;">{thumb}</div>'
        f'<div style="flex:1;min-width:0;">'
        f'<div class="ls-head" style="display:flex;'
        f'justify-content:space-between;align-items:baseline;">{head_html}'
        f'<span style="font-family:{MONO};font-size:12px;color:{color};">'
        f"{label} · {fetched}</span></div>"
        f'<div style="font-size:13px;color:{INK};margin:6px 0 8px;">'
        f'{short or t("catalog.no_data_row")}</div>'
        f"{plate_html}"
        f"{ruler}"
        f'<div style="margin-top:6px;">{chips}</div>'
        f"{badges_html}</div></div>",
        unsafe_allow_html=True,
    )

    # раскрытие с деталями — под карточкой (st.expander внутрь HTML
    # не вставить), подписано ASIN'ом, чтобы не терялась связь в списке
    if own_issues:
        with st.expander(t("issue.details_title", asin=asin)):
            issue_details(AIDX.get(asin) or [], str(r["sku_group"] or ""))

if pages > 1:
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    def _page_list(cur: int, total: int) -> list:
        """Номера страниц с многоточием: 1 … 4 5 [6] 7 8 … 37"""
        if total <= 7:
            return list(range(1, total + 1))
        pages_set = {1, total, cur, cur - 1, cur + 1}
        pages_set = {p for p in pages_set if 1 <= p <= total}
        out, prev = [], 0
        for p in sorted(pages_set):
            if prev and p - prev > 1:
                out.append("…")
            out.append(p)
            prev = p
        return out

    nav = _page_list(page, pages)

    # Колонки Streamlit размазывают узкие кнопки на всю ширину контейнера
    # (широкий дашборд) — отсюда рваные зазоры. Заворачиваем блок в
    # container(key=...) и таргетируем его CSS: колонки сжимаются по
    # контенту и центрируются, кнопки одной высоты и без лишних полей.
    st.markdown(
        f"""
        <style>
        .st-key-cat_pager div[data-testid="stHorizontalBlock"] {{
            justify-content: center;
            gap: 6px;
            flex-wrap: wrap;
        }}
        .st-key-cat_pager div[data-testid="column"] {{
            width: auto !important;
            flex: 0 0 auto !important;
            min-width: 0 !important;
        }}
        .st-key-cat_pager button {{
            min-width: 40px !important;
            padding: 4px 12px !important;
        }}
        .st-key-cat_pager button:disabled {{
            color: {ACCENT} !important;
            border-color: {BORDER} !important;
            font-weight: 700 !important;
            opacity: 1 !important;
            background: {CARD} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="cat_pager"):
        cols = st.columns(len(nav) + 2)

        if cols[0].button(t("list.prev"), disabled=page <= 1, key="cat_prev"):
            st.session_state["cat_page"] = page - 1
            st.rerun()

        for i, p in enumerate(nav):
            with cols[i + 1]:
                if p == "…":
                    st.button("…", disabled=True, key=f"cat_dots_{i}")
                elif p == page:
                    st.button(str(p), disabled=True, key=f"cat_pg_{p}")
                else:
                    if st.button(str(p), key=f"cat_pg_{p}"):
                        st.session_state["cat_page"] = p
                        st.rerun()

        if cols[-1].button(t("list.next"), disabled=page >= pages, key="cat_next"):
            st.session_state["cat_page"] = page + 1
            st.rerun()
