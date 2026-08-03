# -*- coding: utf-8 -*-
"""
services/seo.py — поисковый вес фраз и Coverage Score.

Идея: не «сколько фраз влезло в 75 символов», а «сколько поискового веса
сохранилось». Вес берётся из Brand Analytics SQP (реальные показы, клики,
покупки), а не из догадок модели.

Четыре типа фраз:
  must_keep  — по фразе есть покупки: терять нельзя
  preferred  — есть клики, покупок ещё нет: сохранить, если влезает
  compress   — только показы: можно сжать («1500 mAh» → «1.5 Ah»)
  forbid     — чужой бренд или нерелевантный запрос: не пускать в тайтл
"""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from services.db import get_conn

TIERS = ["must_keep", "preferred", "compress", "forbid"]
TIER_LABEL = {
    "must_keep": "Must Keep",
    "preferred": "Preferred",
    "compress": "Compress",
    "forbid": "Forbid",
}
TIER_COLOR = {
    "must_keep": ("#DCEEE0", "#2F6B3A"),
    "preferred": ("#E8EEF7", "#2A4A7B"),
    "compress": ("#FAEEDA", "#854F0B"),
    "forbid": ("#FCEBEB", "#A32D2D"),
}

# бренды конкурентов: попадание = forbid
COMPETITOR_BRANDS = {
    "bosch", "makita", "dewalt", "milwaukee", "einhell", "parkside",
    "black+decker", "black decker", "ryobi", "hikoki", "metabo", "stanley",
    "hilti", "worx", "skil", "aeg", "festool", "total", "ingco",
}

# сжатия, безопасные по смыслу
COMPRESSIONS = [
    (r"(\d+)\s*000\s*mah", lambda m: f"{int(m.group(1))} Ah"),
    (r"(\d+)[.,](\d)\s*0*\s*ah", lambda m: f"{m.group(1)},{m.group(2)} Ah"),
    (r"\bmilímetros?\b|\bmillimeters?\b|\bmillimeter\b", lambda m: "mm"),
    (r"\bnewton[- ]metros?\b|\bnewton[- ]meters?\b", lambda m: "Nm"),
    (r"\bvoltios?\b|\bvolts?\b", lambda m: "V"),
    (r"\bvatios?\b|\bwatts?\b", lambda m: "W"),
    (r"\bcentímetros?\b|\bcentimeters?\b", lambda m: "cm"),
    (r"\bkilogramos?\b|\bkilograms?\b", lambda m: "kg"),
    (r"\bincluye\b|\bincluding\b|\bincluded\b", lambda m: "+"),
]


@st.cache_data(ttl=300)
def load_sqp(asin: str, marketplace: str, weeks: int = 4) -> pd.DataFrame:
    """Агрегат SQP по ASIN за последние N недель."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT search_query,
                   max(search_query_volume)   AS volume,
                   sum(impressions_asin)      AS impressions,
                   sum(clicks_asin)           AS clicks,
                   sum(purchases_asin)        AS purchases,
                   avg(impressions_share)     AS imp_share
            FROM sqp_reports
            WHERE asin = %(asin)s AND marketplace = %(mp)s
              AND reporting_date >= current_date - %(days)s
            GROUP BY search_query
            ORDER BY sum(purchases_asin) DESC NULLS LAST,
                     sum(clicks_asin) DESC NULLS LAST,
                     max(search_query_volume) DESC NULLS LAST
            """,
            conn, params={"asin": asin, "mp": marketplace, "days": weeks * 7},
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def _norm(s: str) -> str:
    s = str(s).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def guess_tier(row: pd.Series, product_title: str) -> str:
    """Тип фразы по фактам SQP, без участия ИИ.

    Осторожно с forbid: у молодого листинга кликов нет даже по правильным
    запросам, поэтому «показы без кликов» — НЕ повод запрещать фразу.
    В forbid уходит только то, что заведомо не наше: чужие бренды и
    запросы, слова которых не пересекаются с названием товара.
    """
    q = str(row.get("search_query", "")).lower()

    if any(b in q for b in COMPETITOR_BRANDS):
        return "forbid"

    purchases = float(row.get("purchases") or 0)
    clicks = float(row.get("clicks") or 0)
    impressions = float(row.get("impressions") or 0)

    if purchases > 0:
        return "must_keep"
    if clicks > 0:
        return "preferred"

    # нерелевантность: ни одно значимое слово запроса не встречается в тайтле
    title_words = set(_norm(product_title).split())
    q_words = [w for w in _norm(q).split() if len(w) > 3]
    if q_words and not any(w in title_words for w in q_words):
        return "forbid"

    if impressions >= 100:
        return "preferred"   # Amazon считает нас релевантными — стоит удержать
    return "compress"


def phrase_weight(row: pd.Series) -> float:
    """Вес фразы: покупки важнее кликов, клики важнее показов.

    Смысл коэффициентов: одна покупка стоит как 20 кликов и как 200 показов —
    так вес отражает деньги, а не видимость.
    """
    purchases = float(row.get("purchases") or 0)
    clicks = float(row.get("clicks") or 0)
    impressions = float(row.get("impressions") or 0)
    volume = float(row.get("volume") or 0)
    return purchases * 200 + clicks * 10 + impressions * 0.05 + volume * 0.001


def compress_phrase(text: str) -> str:
    """Безопасное сжатие: смысл сохраняется, символы экономятся."""
    out = text
    for pattern, repl in COMPRESSIONS:
        out = re.sub(pattern, repl, out, flags=re.I)
    return re.sub(r"\s{2,}", " ", out).strip()


def phrase_present(phrase: str, text: str) -> bool:
    """Фраза считается сохранённой, если все её значимые слова есть в тексте."""
    t = _norm(text)
    words = [w for w in _norm(phrase).split() if len(w) > 2]
    if not words:
        return False
    return all(w in t for w in words)


def coverage(df: pd.DataFrame, title: str, highlights: str = "") -> dict:
    """Coverage Score: доля сохранённого поискового веса.

    Считается КОДОМ, не моделью: суммируем вес фраз, попавших в результат,
    и делим на вес всех значимых (кроме forbid).
    """
    if df.empty:
        return {"score": None, "kept": [], "lost": [],
                "weight_total": 0.0, "weight_kept": 0.0}

    text = f"{title} {highlights}"
    kept, lost = [], []
    w_total = w_kept = 0.0

    for _, r in df.iterrows():
        tier = r.get("tier") or "compress"
        if tier == "forbid":
            continue
        w = float(r.get("weight") or 0)
        if w <= 0:
            continue
        w_total += w
        if phrase_present(r["search_query"], text):
            w_kept += w
            kept.append((r["search_query"], w, tier))
        else:
            lost.append((r["search_query"], w, tier))

    score = round(w_kept / w_total * 100) if w_total else None
    lost.sort(key=lambda x: -x[1])
    kept.sort(key=lambda x: -x[1])
    return {"score": score, "kept": kept, "lost": lost,
            "weight_total": w_total, "weight_kept": w_kept}


def build_keyword_table(asin: str, marketplace: str,
                        product_title: str, weeks: int = 4,
                        top_n: int = 25) -> pd.DataFrame:
    """Таблица фраз с типом и весом — основа разметки перед генерацией."""
    df = load_sqp(asin, marketplace, weeks)
    if df.empty:
        return df
    df = df.head(top_n).copy()
    df["tier"] = df.apply(lambda r: guess_tier(r, product_title), axis=1)
    df["weight"] = df.apply(phrase_weight, axis=1)
    df["in_title"] = df["search_query"].apply(
        lambda q: phrase_present(q, product_title))
    return df.sort_values("weight", ascending=False)


def save_overrides(asin: str, marketplace: str, rows: list[dict]) -> None:
    """Сохраняет ручные правки типов фраз."""
    conn = get_conn()
    with conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO protected_keywords
                    (asin, marketplace, phrase, phrase_type, tier, weight,
                     source, auto_source)
                VALUES (%s,%s,%s,%s,%s,%s,'manual','sqp')
                ON CONFLICT DO NOTHING
                """,
                (asin, marketplace, r["phrase"],
                 "forbid" if r["tier"] == "forbid" else "keep",
                 r["tier"], r.get("weight")))
    conn.close()
    st.cache_data.clear()
