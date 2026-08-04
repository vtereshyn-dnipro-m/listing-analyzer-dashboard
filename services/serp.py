# -*- coding: utf-8 -*-
"""
services/serp.py — превью выдачи и читаемость тайтла.

Два разных читателя у одного листинга:
  · человек сканирует выдачу за 1–2 фиксации взгляда (~30 символов),
    цепляясь за цифры и разделители;
  · ИИ-ассистент (Rufus, COSMO) парсит текст на факты «атрибут — значение».

Отсюда деление 75/125: title под человеческий скан, Item Highlights —
под машинный разбор. Модуль считает обе стороны и рисует превью.
"""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from i18n import t
from services.db import get_conn

# сколько символов реально видно в выдаче
VISIBLE_MOBILE = 60
VISIBLE_DESKTOP = 110
FIRST_GLANCE = 30        # зона 1–2 фиксаций взгляда

INK, MUTED, BORDER, CARD = "#1A1815", "#57534A", "#E7E4DD", "#FFFFFF"
OK_BG, OK_TEXT = "#DCEEE0", "#2F6B3A"
WARN_BG, WARN_TEXT = "#FAEEDA", "#854F0B"
CUT_BG = "#FCE8DC"

# единицы измерения — визуальные якоря, за них цепляется взгляд
UNIT_RE = re.compile(
    r"\b\d+[.,]?\d*\s?(?:V|W|Ah|mAh|Nm|mm|cm|m|kg|g|L|RPM|A|Hz|"
    r"in|pcs|uds|pz|шт)\b", re.I)
# разделитель — только знак, окружённый пробелами: иначе дефис
# внутри модели (CD-200BC) ломает подсчёт смысловых блоков
SPLIT_RE = re.compile(r",|;|\s[·—–\-|/]\s")


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def readability(title: str) -> dict:
    """Метрики человеческого восприятия тайтла."""
    t = str(title or "")
    words = [w for w in re.split(r"\s+", t) if w]
    anchors = UNIT_RE.findall(t)
    chunks = [p.strip() for p in SPLIT_RE.split(t) if p.strip()]
    head = t[:FIRST_GLANCE]
    return {
        "length": len(t),
        "words": len(words),
        "anchors": len(anchors),
        "anchor_list": anchors[:6],
        "chunks": len(chunks),
        "longest_word": max((len(w) for w in words), default=0),
        "head": head,
        "tail": t[FIRST_GLANCE:],
        "head_words": [w for w in re.split(r"\s+", head) if w],
    }


def facts_extracted(title: str, highlights: str = "") -> dict:
    """Сколько фактов «атрибут — значение» может вытащить ИИ."""
    text = f"{title} {highlights}"
    units = UNIT_RE.findall(text)
    # пары «слово + число с единицей» — то, что парсится однозначно
    pairs = re.findall(
        r"([A-Za-zÀ-ÿА-Яа-я]{3,}[\w\s]{0,12}?)\s(\d+[.,]?\d*\s?"
        r"(?:V|W|Ah|mAh|Nm|mm|cm|kg|g|L|RPM))", text, re.I)
    model = re.findall(r"\b[A-Z]{2,}[-–]?\d{2,}[A-Z]{0,3}\b", text)
    return {
        "units": len(units),
        "pairs": [(a.strip(), b.strip()) for a, b in pairs][:8],
        "model": model[0] if model else None,
        "total": len(units) + (1 if model else 0),
    }


def render_serp_row(title: str, limit: int, label: str, note_ok: str) -> str:
    """Одна карточка выдачи: видимая часть зелёным, обрезанная — оранжевым."""
    t = str(title or "")
    visible, cut = t[:limit], t[limit:]
    body = (f'<span style="background:{OK_BG};">{esc(visible)}</span>'
            + (f'<span style="background:{CUT_BG};color:{MUTED};">'
               f'{esc(cut)}…</span>' if cut else ""))
    note = (f'<span style="color:{WARN_TEXT};">{t("serp.cut", n=len(cut))}</span>'
            if cut else f'<span style="color:{OK_TEXT};">{note_ok}</span>')
    return (
        f'<div style="background:{CARD};border:1px solid {BORDER};'
        f'border-radius:10px;padding:12px;margin-bottom:8px;">'
        f'<div style="font-size:12.5px;font-weight:700;margin-bottom:6px;">'
        f'{label}</div>'
        f'<div style="font-size:12.5px;line-height:1.4;">{body}</div>'
        f'<div style="border-top:1px dashed {BORDER};margin-top:8px;'
        f'padding-top:6px;font-size:11.5px;">{note}</div></div>'
    )


def render_first_glance(title: str, r: dict) -> str:
    """Зона первого взгляда: первые 30 символов отдельно."""
    return (
        f'<div style="background:{CARD};border:1px solid {BORDER};'
        f'border-radius:10px;padding:12px 14px;margin-bottom:8px;">'
        f'<div style="font-size:12.5px;font-weight:700;margin-bottom:8px;">'
        f'{t("serp.glance", n=FIRST_GLANCE)}</div>'
        f'<div style="font-family:var(--ls-mono);font-size:12.5px;'
        f'line-height:1.9;">'
        f'<span style="background:{OK_BG};padding:2px 3px;">'
        f'{esc(r["head"])}</span>'
        f'<span style="background:#F1EFE9;padding:2px 3px;color:{MUTED};">'
        f'{esc(r["tail"])}</span></div>'
        f'<div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;'
        f'font-size:11px;">'
        f'<span style="background:{OK_BG if r["anchors"] else WARN_BG};'
        f'color:{OK_TEXT if r["anchors"] else WARN_TEXT};border-radius:5px;'
        f'padding:2px 8px;">{t("serp.anchors")}: '
        f'{" · ".join(r["anchor_list"]) if r["anchors"] else t("chk.none")}</span>'
        f'<span style="background:{OK_BG if r["chunks"] >= 3 else WARN_BG};'
        f'color:{OK_TEXT if r["chunks"] >= 3 else WARN_TEXT};'
        f'border-radius:5px;padding:2px 8px;">{t("serp.chunks")}: {r["chunks"]}</span>'
        f'<span style="background:{OK_BG if r["longest_word"] <= 14 else WARN_BG};'
        f'color:{OK_TEXT if r["longest_word"] <= 14 else WARN_TEXT};'
        f'border-radius:5px;padding:2px 8px;">{t("serp.longest")}: '
        f'{r["longest_word"]}</span></div></div>'
    )


def render_ai_view(f: dict) -> str:
    """Что вытащит ИИ-ассистент покупателя."""
    pairs = "".join(
        f'<div>· {esc(a)} → <code style="background:#F1EFE9;padding:0 4px;">'
        f'{esc(b)}</code></div>' for a, b in f["pairs"]) or (
        f'<div style="color:{WARN_TEXT};">{t("serp.no_pairs")}</div>')
    model = (f'<div>· {t("serp.model")} → <code style="background:#F1EFE9;'
             f'padding:0 4px;">{esc(f["model"])}</code></div>'
             if f["model"] else "")
    return (
        f'<div style="background:{CARD};border:1px solid {BORDER};'
        f'border-left:3px solid #E8590C;border-radius:0 10px 10px 0;'
        f'padding:12px 14px;">'
        f'<div style="font-size:12.5px;font-weight:700;margin-bottom:8px;">'
        f'{t("serp.ai_view")}</div>'
        f'<div style="font-size:12px;line-height:1.7;">{pairs}{model}</div>'
        f'<div style="font-size:11.5px;color:{MUTED};margin-top:6px;">'
        f'{t("serp.facts", n=f["total"])}</div></div>'
    )


@st.cache_data(ttl=600)
def load_competitors(asin: str, marketplace: str, limit: int = 3) -> pd.DataFrame:
    """Конкуренты из матрицы того же маркетплейса — для сравнения в выдаче."""
    try:
        conn = get_conn()
        df = pd.read_sql(
            """
            SELECT DISTINCT ON (m.asin)
                   m.asin, s.title, s.review_count,
                   s.raw->>'price' AS price,
                   s.raw->>'average_rating' AS rating
            FROM product_matrix m
            JOIN LATERAL (
                SELECT title, review_count, raw FROM listing_snapshots s
                WHERE s.asin = m.asin AND s.marketplace = m.marketplace
                  AND s.ok = TRUE AND s.title <> ''
                ORDER BY s.fetched_at DESC LIMIT 1
            ) s ON TRUE
            WHERE m.marketplace = %(mp)s AND m.is_competitor = TRUE
            LIMIT %(lim)s
            """,
            conn, params={"mp": marketplace, "lim": limit},
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()
